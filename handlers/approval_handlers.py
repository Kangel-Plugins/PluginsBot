import html
import json
import os
import re
import shutil
import hashlib
import asyncio
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup

from PluginsBot.config import (
    GROUP_ID,
    PLUGINS_DIR,
    REPO_PATH,
    STORE_JSON_FILE,
    PRIVATE_KEY_PATH,
    STORE_RAW_URL,
)
from PluginsBot.utils.store_utils import add_plugin_to_store_json, get_plugin_filename_by_id
from PluginsBot.utils.git_utils import commit_and_push
from PluginsBot.utils.notification_utils import send_plugin_update_notification
from PluginsBot.utils.crypto_utils import load_private_key, sign_plugin
from PluginsBot.handlers.command_handlers import get_category_label
from PluginsBot.utils.emoji_utils import (
    make_inline_button,
    check_and_update_from_message,
    ID_CROSS,
    ID_BACK,
    EMOJI_CROSS,
    EMOJI_CHECK,
    EMOJI_PACKAGE,
    EMOJI_MEMO,
    EMOJI_USER,
    EMOJI_MESSAGES_TEXT,
    EMOJI_CLIPBOARD,
    EMOJI_DEVELOPER,
    EMOJI_PIN,
    EMOJI_MOBILE,
    EMOJI_MOBILE_ARROW,
    EMOJI_FOLDER,
    EMOJI_CHART_TEXT,
    EMOJI_FILE,
    EMOJI_LIBRARY_TEXT,
    EMOJI_LINK,
)

router = Router()

LEGACY_DIR = os.path.join(REPO_PATH, "legacy_versions")

pending_rejections = {}

_private_key = None
try:
    if os.path.exists(PRIVATE_KEY_PATH):
        _private_key = load_private_key(PRIVATE_KEY_PATH)
        print(f"✅ Загружен приватный ключ: {PRIVATE_KEY_PATH}")
except Exception as e:
    print(f"⚠️ Ошибка загрузки приватного ключа: {e}")


def _move_old_version_to_legacy(plugin_id: str, old_filename: str) -> bool:
    try:
        old_path = os.path.join(PLUGINS_DIR, old_filename)
        if not os.path.exists(old_path):
            print(f"⚠️ Старый файл не найден: {old_path}")
            return False

        subdir = os.path.join(LEGACY_DIR, plugin_id)
        os.makedirs(subdir, exist_ok=True)

        def _file_hash(path: str) -> str:
            sha256_hash = hashlib.sha256()
            with open(path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()

        file_hash = _file_hash(old_path)

        with open(STORE_JSON_FILE, "r", encoding="utf-8") as f:
            store_data = json.load(f)

        if plugin_id not in store_data:
            store_data[plugin_id] = {}

        entry = store_data[plugin_id]

        existing_hashes = set()
        for v_info in entry.get("legacy_version", {}).values():
            existing_hashes.add(v_info.get("hash", ""))

        if file_hash in existing_hashes:
            print(f"⚠️ Файл {old_filename} уже есть в legacy (хеш совпадает), пропускаем")
            os.remove(old_path)
            return True

        version = str(entry.get("version", "unknown"))
        base, ext = os.path.splitext(old_filename)
        ext = ext or ".plugin"

        safe_version = re.sub(r'[\\/:*?"<>| ]+', '_', version).strip('_') or "unknown"
        archive_name = f"{base}_v{safe_version}{ext}"

        dst = os.path.join(subdir, archive_name)
        counter = 1
        while os.path.exists(dst) and _file_hash(dst) != file_hash:
            archive_name = f"{base}_v{safe_version}_{counter}{ext}"
            dst = os.path.join(subdir, archive_name)
            counter += 1

        if not os.path.exists(dst):
            shutil.copy2(old_path, dst)

        legacy_signature = None
        if _private_key:
            try:
                legacy_signature = sign_plugin(_private_key, plugin_id, version, dst)
            except Exception:
                pass

        if "legacy_version" not in entry:
            entry["legacy_version"] = {}

        legacy_entry = {
            "url": f"{STORE_RAW_URL}/legacy_versions/{plugin_id}/{archive_name}",
            "hash": file_hash
        }
        if legacy_signature:
            legacy_entry["signature"] = legacy_signature
        entry["legacy_version"][version] = legacy_entry

        with open(STORE_JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(store_data, f, indent=4, ensure_ascii=False)

        os.remove(old_path)

        print(f"✅ Старая версия {old_filename} перемещена в legacy_versions/{plugin_id}/{archive_name}")
        return True

    except Exception as e:
        print(f"❌ Ошибка при перемещении в legacy: {e}")
        return False


@router.callback_query(F.data.startswith("approve_"))
async def handle_approve(call: CallbackQuery, bot: Bot, pending_submissions: dict):
    if call.message.chat.id != GROUP_ID:
        await call.answer("❌ Команда доступна только в группе", show_alert=True)
        return

    submission_id = int(call.data.split("_")[1])

    if submission_id not in pending_submissions:
        await call.answer("❌ Заявка не найдена", show_alert=True)
        return

    submission = pending_submissions[submission_id]
    metadata = submission["metadata"]
    plugin_id = metadata.get("id")
    dependencies = submission["dependencies"]

    try:
        plugin_filename = submission.get("plugin_file", f"{plugin_id}.plugin")
        is_elyx = submission.get("is_elyx")
        if is_elyx is None:
            is_elyx = plugin_filename.lower().endswith(('.zip', '.elyx', '.eaf'))
        if is_elyx:
            plugin_filename = f"{plugin_id}.eaf"
        else:
            plugin_filename = f"{plugin_id}.plugin"

        existing_plugin_filename = get_plugin_filename_by_id(plugin_id)
        plugin_path = os.path.join(PLUGINS_DIR, plugin_filename)
        is_new_plugin = existing_plugin_filename is None and not os.path.exists(plugin_path)

        if existing_plugin_filename:
            if not _move_old_version_to_legacy(plugin_id, existing_plugin_filename):
                print(f"⚠️ Не удалось переместить {existing_plugin_filename} в legacy, но продолжаем")

        temp_path = submission.get("temp_path")
        if temp_path and os.path.exists(temp_path):
            shutil.copy2(temp_path, plugin_path)
            try:
                os.remove(temp_path)
            except Exception:
                pass
        elif "plugin_content" in submission:
            content = submission["plugin_content"]
            if is_elyx or isinstance(content, bytes):
                with open(plugin_path, "wb") as f:
                    f.write(content if isinstance(content, bytes) else content.encode("utf-8"))
            else:
                with open(plugin_path, "w", encoding="utf-8") as f:
                    f.write(content)

        url = f"{STORE_RAW_URL}/Plugins/{plugin_filename}"
        status = submission.get("status", "plugin")

        if not add_plugin_to_store_json(plugin_id, url, dependencies, plugin_filename, status=status):
            error_msg = f"❌ Ошибка при добавлении {plugin_id} в store.json (смотри консоль)"
            print(f"[APPROVE] {error_msg}")
            await call.answer(error_msg, show_alert=True)
            return

        if _private_key and os.path.exists(plugin_path):
            try:
                version = metadata.get('version', '1.0.0')
                sig = sign_plugin(_private_key, plugin_id, version, plugin_path)
                with open(STORE_JSON_FILE, "r", encoding="utf-8") as f:
                    store_data = json.load(f)
                if plugin_id in store_data:
                    store_data[plugin_id]["signature"] = sig
                    with open(STORE_JSON_FILE, "w", encoding="utf-8") as f:
                        json.dump(store_data, f, indent=4, ensure_ascii=False)
                    print(f"✅ Подпись добавлена для {plugin_id} v{version}")
            except Exception as e:
                print(f"⚠️ Ошибка подписи {plugin_id}: {e}")

        action_text = "добавлен" if is_new_plugin else "обновлен"
        version = metadata.get('version', '1.0.0')

        success, commit_message = await asyncio.to_thread(commit_and_push, plugin_id, version, is_new_plugin)

        if not success:
            await call.answer(f"⚠️ Плагин {action_text}, но нет новых изменений для коммита", show_alert=True)
        else:
            await call.answer(f"✅ Плагин успешно {action_text}!", show_alert=True)

        try:
            await call.message.delete()
            print(f"✅ Сообщение о заявке удалено")
        except Exception as delete_error:
            print(f"⚠️ Не удалось удалить сообщение: {delete_error}")

        await send_plugin_update_notification(
            bot,
            plugin_id,
            metadata.get('name', 'Unknown'),
            metadata.get('author', 'Unknown'),
            version,
            is_new_plugin,
            status=status,
            description=metadata.get('description'),
        )

        if commit_message:
            try:
                sent = await bot.send_message(
                    chat_id=submission["user_id"],
                    text=(
                        f"{EMOJI_CHECK} <b>Плагин одобрен!</b>\n\n"
                        f"Ваш плагин <code>{html.escape(str(plugin_id))}</code> успешно {action_text} в хранилище.\n"
                        f"Коммит: {html.escape(str(commit_message))}"
                    ),
                )
                check_and_update_from_message(sent)
                print(f"✅ Уведомление об одобрении отправлено пользователю {submission['user_id']}")
            except Exception as notify_error:
                print(f"⚠️ Не удалось отправить уведомление пользователю {submission['user_id']}: {notify_error}")

        del pending_submissions[submission_id]

    except Exception as e:
        print(f"Ошибка при одобрении: {e}")
        error_msg = str(e)
        if len(error_msg) > 200:
            error_msg = error_msg[:197] + "..."
        await call.answer(f"❌ Ошибка: {error_msg}", show_alert=True)


@router.callback_query(F.data.startswith("reject_"))
async def handle_reject(call: CallbackQuery, bot: Bot, pending_submissions: dict):
    if call.message.chat.id != GROUP_ID:
        await call.answer("❌ Команда доступна только в группе", show_alert=True)
        return

    submission_id = int(call.data.split("_")[1])

    if submission_id not in pending_submissions:
        await call.answer("❌ Заявка не найдена", show_alert=True)
        return

    submission = pending_submissions[submission_id]
    plugin_id = submission["metadata"].get("id")
    plugin_name = submission["metadata"].get("name", "N/A")
    username = submission.get("username", "Unknown")

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                make_inline_button(
                    "Назад",
                    callback_data=f"rejx_{submission_id}",
                    emoji_id=ID_BACK,
                    fallback_emoji="◀️",
                ),
                make_inline_button(
                    "Да, отклонить (без причины)",
                    callback_data=f"rejc_{submission_id}",
                    emoji_id=ID_CROSS,
                    fallback_emoji="❌",
                    style="danger",
                ),
            ]
        ]
    )

    rejection_caption = (
        f"{EMOJI_CROSS} <b>Отклонение плагина</b>\n\n"
        f"{EMOJI_PACKAGE} ID: <code>{html.escape(str(plugin_id))}</code>\n"
        f"{EMOJI_MEMO} Название: {html.escape(str(plugin_name))}\n"
        f"{EMOJI_DEVELOPER} Автор: @{html.escape(str(username))}\n\n"
        f"Введите причину отказа следующим сообщением в чат или подтвердите кнопкой."
    )

    try:
        await call.message.edit_caption(caption=rejection_caption, reply_markup=keyboard)
    except Exception:
        await call.message.edit_reply_markup(reply_markup=keyboard)

    rejection_info = {
        "submission_id": submission_id,
        "group_message_id": call.message.message_id,
        "chat_id": call.message.chat.id,
        "admin_user": call.from_user,
    }

    pending_rejections[call.message.message_id] = rejection_info
    pending_rejections[f"sub_{submission_id}"] = rejection_info

    await call.answer("Введите причину отказа сообщением в чат или подтвердите")


@router.callback_query(F.data.startswith("rejc_"))
async def handle_reject_confirm(call: CallbackQuery, bot: Bot, pending_submissions: dict):
    try:
        submission_id = int(call.data.split("_")[1])
    except (IndexError, ValueError):
        await call.answer("❌ Заявка не найдена", show_alert=True)
        return

    sub_key = f"sub_{submission_id}"
    pending = pending_rejections.pop(sub_key, None)
    if pending:
        card_id = pending.get("group_message_id")
        if card_id:
            pending_rejections.pop(card_id, None)

    if submission_id not in pending_submissions:
        await call.answer("❌ Заявка не найдена", show_alert=True)
        return

    try:
        await call.message.delete()
    except Exception:
        pass

    submission = pending_submissions[submission_id]
    admin_user = call.from_user
    await _execute_rejection(bot, pending_submissions, submission_id, "Причина не указана", submission, call.message, admin_user)
    await call.answer("✅ Плагин отклонён")


@router.callback_query(F.data.startswith("rejx_"))
async def handle_reject_cancel(call: CallbackQuery, bot: Bot, pending_submissions: dict):
    try:
        submission_id = int(call.data.split("_")[1])
    except (IndexError, ValueError):
        await call.answer("❌ Заявка не найдена", show_alert=True)
        return

    sub_key = f"sub_{submission_id}"
    pending = pending_rejections.pop(sub_key, None)
    if pending:
        card_id = pending.get("group_message_id")
        if card_id:
            pending_rejections.pop(card_id, None)

    if submission_id not in pending_submissions:
        await call.answer("❌ Заявка не найдена", show_alert=True)
        return

    from PluginsBot.handlers.plugin_handlers import create_approval_keyboard

    submission = pending_submissions[submission_id]
    metadata = submission["metadata"]
    needs_status = not submission.get("status")

    info_text = _build_submission_caption(metadata, submission)

    try:
        await call.message.edit_caption(
            caption=info_text,
            reply_markup=create_approval_keyboard(submission_id, needs_status=needs_status),
        )
    except Exception:
        await call.message.edit_reply_markup(
            reply_markup=create_approval_keyboard(submission_id, needs_status=needs_status),
        )
    await call.answer("Отменено")


def _find_pending_rejection(message: Message) -> dict | None:
    if not message.text or message.text.startswith("/"):
        return None

    # 1. Если ответили напрямую на карточку заявки
    if message.reply_to_message:
        reply_id = message.reply_to_message.message_id
        pending = pending_rejections.get(reply_id)
        if pending and isinstance(pending, dict):
            initiator = pending.get("admin_user")
            if initiator and message.from_user.id != initiator.id:
                return None
            return pending

    # 2. Обычное сообщение в чате от того, кто нажал «Отклонить»
    user_candidates = [
        v for k, v in pending_rejections.items()
        if isinstance(k, str) and k.startswith("sub_") and isinstance(v, dict)
        and v.get("admin_user") and v.get("admin_user").id == message.from_user.id
        and v.get("chat_id") == message.chat.id
    ]
    if user_candidates:
        return user_candidates[-1]

    return None


def _is_rejection_reason_message(message: Message) -> bool:
    if message.chat.id != GROUP_ID:
        return False
    return _find_pending_rejection(message) is not None


@router.message(_is_rejection_reason_message)
async def handle_reject_reason(message: Message, bot: Bot, pending_submissions: dict):
    pending = _find_pending_rejection(message)
    if not pending:
        return

    submission_id = pending["submission_id"]
    group_message_id = pending.get("group_message_id")
    initiator = pending.get("admin_user")
    admin_user = initiator or message.from_user

    # Удаляем ожидания отклонения для данной заявки
    pending_rejections.pop(f"sub_{submission_id}", None)
    if group_message_id:
        pending_rejections.pop(group_message_id, None)

    if submission_id not in pending_submissions:
        await message.reply(f"{EMOJI_CROSS} Заявка уже обработана")
        return

    reason = message.text.strip() or "Причина не указана"
    submission = pending_submissions[submission_id]

    try:
        await message.delete()
    except Exception:
        pass

    if group_message_id:
        try:
            await bot.delete_message(message.chat.id, group_message_id)
        except Exception:
            pass

    await _execute_rejection(bot, pending_submissions, submission_id, reason, submission, message, admin_user)


async def _execute_rejection(bot: Bot, pending_submissions: dict, submission_id: int, reason: str, submission: dict, trigger_message: Message, admin_user):
    plugin_id = submission["metadata"].get("id")
    username = submission.get("username", "Unknown")

    if getattr(admin_user, "username", None):
        admin_display = f"@{admin_user.username}"
    else:
        first = getattr(admin_user, "first_name", "") or ""
        last = getattr(admin_user, "last_name", "") or ""
        full = f"{first} {last}".strip()
        admin_display = full if full else f"ID {admin_user.id}"

    temp_path = submission.get("temp_path")
    if temp_path and os.path.exists(temp_path):
        try:
            os.remove(temp_path)
        except Exception:
            pass

    try:
        sent = await bot.send_message(
            chat_id=submission["user_id"],
            text=(
                f"{EMOJI_CROSS} <b>Плагин отклонён</b>\n\n"
                f"{EMOJI_PACKAGE} ID: <code>{html.escape(str(plugin_id))}</code>\n"
                f"{EMOJI_MESSAGES_TEXT} Причина: {html.escape(reason)}\n"
                f"{EMOJI_USER} Отклонил: {html.escape(admin_display)}\n\n"
                f"Если у вас есть вопросы, обратитесь к администраторам."
            ),
        )
        check_and_update_from_message(sent)
    except Exception as e:
        print(f"⚠️ Не удалось отправить уведомление пользователю {submission['user_id']}: {e}")

    try:
        sent2 = await bot.send_message(
            chat_id=trigger_message.chat.id,
            text=(
                f"{EMOJI_CROSS} <b>Отклонено</b>: <code>{html.escape(str(plugin_id))}</code>\n"
                f"{EMOJI_MESSAGES_TEXT} Причина: {html.escape(reason)}\n"
                f"{EMOJI_USER} Отклонил: {html.escape(admin_display)}"
            ),
        )
        check_and_update_from_message(sent2)
    except Exception:
        pass

    if submission_id in pending_submissions:
        del pending_submissions[submission_id]


def _build_submission_caption(metadata, submission):
    exists = submission.get("status") is not None
    info_text = (
        f"{EMOJI_CLIPBOARD} <b>{'Обновление' if exists else 'Новая заявка'} на плагин</b>\n\n"
        f"{EMOJI_USER} От: @{submission.get('username', 'Unknown')}\n"
        f"{EMOJI_PACKAGE} ID: <code>{html.escape(str(metadata.get('id', 'N/A')))}</code>\n"
        f"{EMOJI_MEMO} Название: {html.escape(str(metadata.get('name', 'N/A')))}\n"
        f"{EMOJI_DEVELOPER} Автор: {html.escape(str(metadata.get('author', 'N/A')))}\n"
        f"{EMOJI_PIN} Версия: {html.escape(str(metadata.get('version', 'N/A')))}\n"
    )

    min_version = metadata.get('min_version')
    if min_version:
        info_text += f"{EMOJI_MOBILE} Min version: {html.escape(str(min_version))}\n"

    app_version = metadata.get('app_version')
    if app_version and app_version != min_version:
        info_text += f"{EMOJI_MOBILE_ARROW} App version: {html.escape(str(app_version))}\n"

    if submission.get("status"):
        info_text += f"{EMOJI_FOLDER} Категория: <b>{get_category_label(submission['status'])}</b>\n"

    if exists:
        info_text += f"{EMOJI_CHART_TEXT} Текущий статус: <b>{html.escape(str(submission.get('status')))}</b>\n"

    description = metadata.get('description')
    if description and str(description).strip():
        desc_str = str(description).replace("\\n", "\n").strip()
        if len(desc_str) > 600:
            desc_str = desc_str[:597] + "..."
        info_text += f"{EMOJI_FILE} Описание:\n<blockquote expandable>{html.escape(desc_str)}</blockquote>\n"

    requirements = metadata.get('requirements')
    if requirements:
        safe_reqs = [html.escape(str(r)) for r in requirements]
        info_text += f"{EMOJI_PACKAGE} Requirements: {', '.join(safe_reqs)}\n"

    dependencies = submission.get("dependencies", [])
    if dependencies:
        safe_deps = [html.escape(str(d)) for d in dependencies]
        info_text += f"{EMOJI_LIBRARY_TEXT} Зависимости: {', '.join(safe_deps)}\n"

    requires = metadata.get('requires')
    if requires:
        req_texts = []
        for r in requires:
            rlabel = str(r.get('id', '?'))
            ver = r.get('min_version')
            if ver:
                rlabel += f" ({html.escape(str(ver))})"
            req_texts.append(html.escape(rlabel))
        info_text += f"{EMOJI_LINK} Требует: {', '.join(req_texts)}\n"

    info_text += f"\n{EMOJI_FILE} Файл: <code>{html.escape(submission.get('plugin_file', 'N/A'))}</code>"
    return info_text
