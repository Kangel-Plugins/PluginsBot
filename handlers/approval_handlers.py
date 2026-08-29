import html
import json
import os
import re
import shutil
import hashlib
from telebot import types

from PluginsBot.config import GROUP_ID, PLUGINS_DIR, REPO_PATH, KNOWN_LIBS, STORE_JSON_FILE
from PluginsBot.utils.store_utils import add_plugin_to_store_json, get_plugin_filename_by_id
from PluginsBot.utils.git_utils import commit_and_push
from PluginsBot.utils.notification_utils import send_plugin_update_notification


LEGACY_DIR = os.path.join(REPO_PATH, "legacy_versions")

pending_rejections = {}


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

        if "legacy_version" not in entry:
            entry["legacy_version"] = {}

        entry["legacy_version"][version] = {
            "url": f"https://raw.githubusercontent.com/KangelPlugins/Plugins-Store/main/legacy_versions/{plugin_id}/{archive_name}",
            "hash": file_hash
        }

        with open(STORE_JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(store_data, f, indent=4, ensure_ascii=False)

        os.remove(old_path)

        print(f"✅ Старая версия {old_filename} перемещена в legacy_versions/{plugin_id}/{archive_name}")
        return True

    except Exception as e:
        print(f"❌ Ошибка при перемещении в legacy: {e}")
        return False


def register_approval_handlers(bot, pending_submissions):

    @bot.callback_query_handler(func=lambda call: call.data.startswith("approve_"))
    def handle_approve(call: types.CallbackQuery):
        if call.message.chat.id != GROUP_ID:
            bot.answer_callback_query(call.id, "❌ Команда доступна только в группе", show_alert=True)
            return

        submission_id = int(call.data.split("_")[1])

        if submission_id not in pending_submissions:
            bot.answer_callback_query(call.id, "❌ Заявка не найдена", show_alert=True)
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

            if is_elyx:
                with open(plugin_path, "wb") as f:
                    f.write(submission["plugin_content"])
            else:
                with open(plugin_path, "w", encoding="utf-8") as f:
                    f.write(submission["plugin_content"])

            url = f"https://raw.githubusercontent.com/KangelPlugins/Plugins-Store/main/Plugins/{plugin_filename}"

            status = submission.get("status", "plugin")
            if not add_plugin_to_store_json(plugin_id, url, dependencies, plugin_filename, status=status):
                error_msg = f"❌ Ошибка при добавлении {plugin_id} в store.json (смотри консоль)"
                print(f"[APPROVE] {error_msg}")
                bot.answer_callback_query(call.id, error_msg, show_alert=True)
                return

            action_text = "добавлен" if is_new_plugin else "обновлен"

            version = metadata.get('version', '1.0.0')
            success, commit_message = commit_and_push(plugin_id, version, is_new_plugin)

            if not success:
                bot.answer_callback_query(call.id, f"⚠️ Плагин {action_text}, но нет новых изменений для коммита", show_alert=True)
            else:
                bot.answer_callback_query(call.id, f"✅ Плагин успешно {action_text}!", show_alert=True)

            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
                print(f"✅ Сообщение о заявке удалено из группы")
            except Exception as delete_error:
                print(f"⚠️ Не удалось удалить сообщение из группы: {delete_error}")

            status = submission.get("status", "plugin")
            send_plugin_update_notification(
                bot,
                plugin_id,
                metadata.get('name', 'Unknown'),
                metadata.get('author', 'Unknown'),
                version,
                is_new_plugin,
                status=status
            )

            if commit_message:
                try:
                    bot.send_message(
                        submission["user_id"],
                        f"✅ <b>Плагин одобрен!</b>\n\n"
                        f"Ваш плагин <code>{html.escape(str(plugin_id))}</code> успешно {action_text} в хранилище.\n"
                        f"Коммит: {html.escape(str(commit_message))}",
                        parse_mode="HTML",
                    )
                    print(f"✅ Уведомление об одобрении отправлено пользователю {submission['user_id']}")
                except Exception as notify_error:
                    print(f"⚠️ Не удалось отправить уведомление пользователю {submission['user_id']}: {notify_error}")

            del pending_submissions[submission_id]

        except Exception as e:
            print(f"Ошибка при одобрении: {e}")

            error_msg = str(e)
            if len(error_msg) > 200:
                error_msg = error_msg[:197] + "..."
            bot.answer_callback_query(call.id, f"❌ Ошибка: {error_msg}", show_alert=True)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("reject_"))
    def handle_reject(call: types.CallbackQuery):
        if call.message.chat.id != GROUP_ID:
            bot.answer_callback_query(call.id, "❌ Команда доступна только в группе", show_alert=True)
            return

        submission_id = int(call.data.split("_")[1])

        if submission_id not in pending_submissions:
            bot.answer_callback_query(call.id, "❌ Заявка не найдена", show_alert=True)
            return

        submission = pending_submissions[submission_id]
        plugin_id = submission["metadata"].get("id")
        plugin_name = submission["metadata"].get("name", "N/A")
        username = submission.get("username", "Unknown")

        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            types.InlineKeyboardButton("❌ Да, отклонить", callback_data=f"rejc_{submission_id}"),
            types.InlineKeyboardButton("◀️ Назад", callback_data=f"rejx_{submission_id}"),
        )

        bot.edit_message_caption(
            caption=(
                f"❌ <b>Отклонение плагина</b>\n\n"
                f"📦 ID: <code>{html.escape(str(plugin_id))}</code>\n"
                f"📝 Название: {html.escape(str(plugin_name))}\n"
                f"👤 Автор: @{html.escape(str(username))}\n\n"
                f"Введите причину отказа следующим сообщением в чат.\n"
                f"Или нажмите «Да, отклонить» для отклонения без причины."
            ),
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=keyboard,
        )

        pending_rejections[call.message.chat.id] = {
            "submission_id": submission_id,
            "group_message_id": call.message.message_id,
            "awaiting_reason": True,
            "admin_user": call.from_user,
        }

        bot.answer_callback_query(call.id, "Введите причину отказа или подтвердите")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("rejc_"))
    def handle_reject_confirm(call: types.CallbackQuery):
        chat_id = call.message.chat.id
        if chat_id not in pending_rejections:
            bot.answer_callback_query(call.id, "❌ Заявка не найдена", show_alert=True)
            return

        pending = pending_rejections.pop(chat_id)
        submission_id = pending["submission_id"]
        group_message_id = pending.get("group_message_id")

        if submission_id not in pending_submissions:
            bot.answer_callback_query(call.id, "❌ Заявка не найдена", show_alert=True)
            return

        if group_message_id:
            try:
                bot.delete_message(chat_id, group_message_id)
            except Exception:
                pass

        submission = pending_submissions[submission_id]
        admin_user = pending.get("admin_user", call.from_user)
        _execute_rejection(bot, pending_submissions, submission_id, "Причина не указана", submission, call.message, admin_user)
        bot.answer_callback_query(call.id, "✅ Плагин отклонён")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("rejx_"))
    def handle_reject_cancel(call: types.CallbackQuery):
        chat_id = call.message.chat.id
        pending_rejections.pop(chat_id, None)

        submission_id = int(call.data.split("_")[1])
        if submission_id not in pending_submissions:
            bot.answer_callback_query(call.id, "❌ Заявка не найдена", show_alert=True)
            return

        from .plugin_handlers import create_approval_keyboard

        submission = pending_submissions[submission_id]
        metadata = submission["metadata"]
        needs_status = not submission.get("status")

        info_text = _build_submission_caption(metadata, submission, pending_submissions)

        bot.edit_message_caption(
            caption=info_text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=create_approval_keyboard(submission_id, needs_status=needs_status),
        )
        bot.answer_callback_query(call.id, "Отменено")

    @bot.message_handler(
        func=lambda m: (
            m.chat.id in pending_rejections
            and pending_rejections[m.chat.id].get("awaiting_reason")
            and m.text
            and not m.text.startswith("/")
        ),
    )
    def handle_reject_reason_text(message: types.Message):
        chat_id = message.chat.id
        if chat_id not in pending_rejections:
            return

        pending = pending_rejections.pop(chat_id)
        submission_id = pending["submission_id"]
        group_message_id = pending.get("group_message_id")

        if submission_id not in pending_submissions:
            bot.reply_to(message, "❌ Заявка уже обработана")
            return

        reason = message.text.strip() or "Причина не указана"
        submission = pending_submissions[submission_id]
        admin_user = pending.get("admin_user", message.from_user)

        try:
            bot.delete_message(chat_id, message.message_id)
        except Exception:
            pass

        if group_message_id:
            try:
                bot.delete_message(chat_id, group_message_id)
            except Exception:
                pass

        _execute_rejection(bot, pending_submissions, submission_id, reason, submission, message, admin_user)


def _execute_rejection(bot, pending_submissions, submission_id, reason, submission, trigger_message, admin_user):
    plugin_id = submission["metadata"].get("id")
    username = submission.get("username", "Unknown")
    admin_name = admin_user.username or str(admin_user.id)

    try:
        bot.delete_message(trigger_message.chat.id, trigger_message.message_id)
    except Exception:
        pass

    try:
        bot.send_message(
            submission["user_id"],
            f"❌ <b>Плагин отклонён</b>\n\n"
            f"📦 ID: <code>{html.escape(str(plugin_id))}</code>\n"
            f"💬 Причина: {html.escape(reason)}\n"
            f"👤 Отклонил: @{html.escape(admin_name)}\n\n"
            f"Если у вас есть вопросы, обратитесь к администраторам.",
            parse_mode="HTML",
        )
    except Exception as e:
        print(f"⚠️ Не удалось отправить уведомление пользователю {submission['user_id']}: {e}")

    try:
        bot.send_message(
            trigger_message.chat.id,
            f"❌ <b>Отклонено</b>: <code>{html.escape(str(plugin_id))}</code>\n"
            f"💬 Причина: {html.escape(reason)}\n"
            f"👤 Отклонил: @{html.escape(admin_name)}",
            parse_mode="HTML",
        )
    except Exception:
        pass

    del pending_submissions[submission_id]


def _build_submission_caption(metadata, submission, pending_submissions=None):
    exists = submission.get("status") is not None
    info_text = (
        f"📋 <b>{'Обновление' if exists else 'Новая заявка'} на плагин</b>\n\n"
        f"👤 От: @{submission.get('username', 'Unknown')}\n"
        f"📦 ID: <code>{html.escape(str(metadata.get('id', 'N/A')))}</code>\n"
        f"📝 Название: {html.escape(str(metadata.get('name', 'N/A')))}\n"
        f"👨‍💻 Автор: {html.escape(str(metadata.get('author', 'N/A')))}\n"
        f"📌 Версия: {html.escape(str(metadata.get('version', 'N/A')))}\n"
    )

    min_version = metadata.get('min_version')
    if min_version:
        info_text += f"📱 Min version: {html.escape(str(min_version))}\n"

    app_version = metadata.get('app_version')
    if app_version and app_version != min_version:
        info_text += f"📲 App version: {html.escape(str(app_version))}\n"

    if submission.get("status"):
        from .command_handlers import CATEGORIES
        label = CATEGORIES.get(submission["status"], submission["status"])
        info_text += f"📂 Категория: <b>{html.escape(label)}</b>\n"

    if exists:
        info_text += f"📊 Текущий статус: <b>{html.escape(str(submission.get('status')))}</b>\n"

    description = metadata.get('description')
    if description:
        desc_preview = description[:200] + "..." if len(description) > 200 else description
        info_text += f"📄 Описание: {html.escape(desc_preview)}\n"

    requirements = metadata.get('requirements')
    if requirements:
        safe_reqs = [html.escape(str(r)) for r in requirements]
        info_text += f"📦 Requirements: {', '.join(safe_reqs)}\n"

    dependencies = submission.get("dependencies", [])
    if dependencies:
        safe_deps = [html.escape(str(d)) for d in dependencies]
        info_text += f"📚 Зависимости: {', '.join(safe_deps)}\n"

    requires = metadata.get('requires')
    if requires:
        req_texts = []
        for r in requires:
            label = str(r.get('id', '?'))
            ver = r.get('min_version')
            if ver:
                label += f" ({html.escape(str(ver))})"
            req_texts.append(html.escape(label))
        info_text += f"🔗 Требует: {', '.join(req_texts)}\n"

    info_text += f"\n📄 Файл: <code>{html.escape(submission.get('plugin_file', 'N/A'))}</code>"
    return info_text
