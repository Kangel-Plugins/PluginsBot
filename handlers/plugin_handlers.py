import os
import re
import html
import tempfile
from pathlib import Path
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, FSInputFile

from PluginsBot.config import GROUP_ID, UPDATES_CHAT_ID
from PluginsBot.handlers.command_handlers import (
    CATEGORIES,
    get_category_label,
    get_category_name,
    category_keyboard,
)
from PluginsBot.utils.plugin_utils import (
    extract_plugin_metadata,
    detect_dependencies,
    extract_elyx_metadata_from_file,
    PluginEncodingError,
)
from PluginsBot.utils.download_utils import (
    is_elyx_plugin,
    plugin_extension,
)
from PluginsBot.utils.store_utils import is_plugin_in_store
from PluginsBot.utils.emoji_utils import (
    make_inline_button,
    check_and_update_from_message,
    ID_CHECK,
    ID_CROSS,
    EMOJI_CROSS,
    EMOJI_CHECK,
    EMOJI_CLIPBOARD,
    EMOJI_USER,
    EMOJI_PACKAGE,
    EMOJI_MEMO,
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

pending_file_data = {}


def create_approval_keyboard(submission_id: int, needs_status: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [
            make_inline_button(
                "Принять",
                callback_data=f"approve_{submission_id}",
                emoji_id=ID_CHECK,
                fallback_emoji="✅",
                style="success",
            ),
            make_inline_button(
                "Отклонить",
                callback_data=f"reject_{submission_id}",
                emoji_id=ID_CROSS,
                fallback_emoji="❌",
                style="danger",
            ),
        ]
    ]

    if needs_status:
        current_row = []
        for key, (name, fallback, emoji_id) in CATEGORIES.items():
            btn = make_inline_button(
                text=name,
                callback_data=f"status_{key}_{submission_id}",
                emoji_id=emoji_id,
                fallback_emoji=fallback,
            )
            current_row.append(btn)
            if len(current_row) == 2:
                rows.append(current_row)
                current_row = []
        if current_row:
            rows.append(current_row)

    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _send_to_group(bot: Bot, pending_submissions: dict, user_id: int):
    if user_id not in pending_file_data:
        return

    data = pending_file_data.pop(user_id)
    category = data.get("status")
    submission_id = data["submission_id"]
    metadata = data["metadata"]

    pending_submissions[submission_id] = data

    info_text = (
        f"{EMOJI_CLIPBOARD} <b>{'Обновление' if data.get('exists') else 'Новая заявка'} на плагин</b>\n\n"
        f"{EMOJI_USER} От: @{data.get('username', 'Unknown')}\n"
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

    if category:
        info_text += f"{EMOJI_FOLDER} Категория: <b>{get_category_label(category)}</b>\n"

    if data.get('exists'):
        info_text += f"{EMOJI_CHART_TEXT} Текущий статус: <b>{html.escape(str(category))}</b>\n"

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

    dependencies = data.get("dependencies", [])
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

    info_text += f"\n{EMOJI_FILE} Файл: <code>{html.escape(data.get('plugin_file', 'N/A'))}</code>"

    pending_submissions[submission_id]["caption_html"] = info_text

    group_message = None
    file_id = data.get("file_id")
    if file_id:
        try:
            group_message = await bot.send_document(
                chat_id=GROUP_ID,
                document=file_id,
                caption=info_text,
                reply_markup=create_approval_keyboard(submission_id, needs_status=not data.get('exists')),
            )
        except Exception as e:
            print(f"⚠️ Не удалось отправить документ по file_id, пробуем через файл: {e}")
            group_message = None

    if not group_message:
        temp_path = data.get("temp_path")
        if not temp_path or not os.path.exists(temp_path):
            print(f"❌ Временный файл не найден: {temp_path}")
            return

        doc = FSInputFile(temp_path, filename=data.get('plugin_file', 'plugin.plugin'))
        group_message = await bot.send_document(
            chat_id=GROUP_ID,
            document=doc,
            caption=info_text,
            reply_markup=create_approval_keyboard(submission_id, needs_status=not data.get('exists')),
        )

    check_and_update_from_message(group_message)
    pending_submissions[submission_id]["group_message_id"] = group_message.message_id


@router.callback_query(F.data.startswith("status_"))
async def handle_status_selection(call: CallbackQuery, pending_submissions: dict):
    data_parts = call.data.split("_")
    new_status = data_parts[1]
    submission_id = int(data_parts[2])

    if submission_id not in pending_submissions:
        await call.answer("❌ Заявка не найдена", show_alert=True)
        return

    pending_submissions[submission_id]["status"] = new_status

    base_html = pending_submissions[submission_id].get("caption_html") or call.message.caption or ""
    status_pattern = re.compile(r"\n?(?:<tg-emoji[^>]*>)?📊(?:</tg-emoji>)? Выбранный статус: <b>.*?</b>")
    base_html = status_pattern.sub("", base_html)

    cat_lbl = get_category_label(new_status)
    info_text = base_html + f"\n{EMOJI_CHART_TEXT} Выбранный статус: <b>{cat_lbl}</b>"

    await call.message.edit_caption(
        caption=info_text,
        reply_markup=create_approval_keyboard(submission_id, needs_status=False),
    )
    await call.answer(f"✅ Статус: {get_category_name(new_status)}")


@router.callback_query(F.data.startswith("cat_"))
async def handle_category_selection(call: CallbackQuery, bot: Bot, pending_submissions: dict):
    user_id = call.from_user.id
    if user_id not in pending_file_data:
        await call.answer("❌ Файл не найден, отправьте плагин заново", show_alert=True)
        return

    category = call.data[len("cat_"):]
    pending_file_data[user_id]["status"] = category

    await _send_to_group(bot, pending_submissions, user_id)

    msg_text = f"{EMOJI_CHECK} Категория: <b>{get_category_label(category)}</b>\n\nЗаявка отправлена в группу на рассмотрение."
    try:
        await call.message.edit_text(msg_text)
    except Exception:
        await call.message.answer(msg_text)

    await call.answer("✅ Заявка отправлена!")


@router.message(F.document)
async def handle_plugin_submission(message: Message, bot: Bot, pending_submissions: dict):
    is_private = message.chat.type == "private"
    is_group = message.chat.id == GROUP_ID
    is_updates = message.chat.id == UPDATES_CHAT_ID

    if is_updates:
        return

    if not is_private and not is_group:
        await message.reply(
            f"{EMOJI_CROSS} Отправь плагин мне в личные сообщения (@KPMAppealBot)"
        )
        return

    if is_private:
        try:
            chat_member = await bot.get_chat_member(UPDATES_CHAT_ID, message.from_user.id)
            if chat_member.status in ("left", "kicked", "restricted"):
                await message.reply(
                    f"{EMOJI_CROSS} Для отправки плагинов необходимо зайти в @KangelPluginsManager"
                )
                return
        except Exception as e:
            print(f"⚠️ Ошибка при проверке членства в чате: {e}")
            await message.reply(
                f"{EMOJI_CROSS} Для отправки плагинов необходимо зайти в @KangelPluginsManager"
            )
            return

    filename = message.document.file_name or ""
    ext = plugin_extension(filename)
    if not ext:
        await message.reply(
            f"{EMOJI_CROSS} Отправь файл плагина (.plugin, .eaf, .elyx, .zip, .eaf.zip, .elyx.zip)\n\n"
            f"<b>Лимиты размера:</b>\n"
            f"• .plugin — до 8 МБ\n"
            f"• Elyx (.eaf / .elyx / .zip) — до 100 МБ"
        )
        return

    try:
        downloaded_file = await download_plugin_file(bot, message.document)

        temp_dir = Path(tempfile.gettempdir()) / "plugins_bot_submissions"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_path = temp_dir / f"{message.from_user.id}_{message.message_id}_{message.document.file_name}"

        with open(temp_path, "wb") as f:
            f.write(downloaded_file)

        header_bytes = downloaded_file[:4]

        is_elyx = is_elyx_plugin(filename)
        if not is_elyx and header_bytes == b'PK\x03\x04':
            is_elyx = True

        if is_elyx:
            try:
                metadata = extract_elyx_metadata_from_file(str(temp_path))
            except PluginEncodingError:
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
                await message.reply(
                    f"{EMOJI_CROSS} Внутри архива есть файл, сохранённый не в UTF-8.\n\n"
                    f"Пересохраните <b>metainfo</b>, <b>refmap</b> и файлы локализации в UTF-8 "
                    f"(в PyCharm/VS Code: File Encoding → UTF-8) и отправьте заново."
                )
                return
            dependencies = []
        else:
            try:
                with open(temp_path, "r", encoding="utf-8") as f:
                    plugin_content = f.read()
            except UnicodeDecodeError:
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
                await message.reply(
                    f"{EMOJI_CROSS} Файл плагина сохранён не в UTF-8.\n\n"
                    f"Пересохраните его в UTF-8 и отправьте заново."
                )
                return
            metadata = extract_plugin_metadata(plugin_content)
            dependencies = detect_dependencies(plugin_content, metadata.get("id"))

        if not metadata.get("id"):
            try:
                os.remove(temp_path)
            except Exception:
                pass
            await message.reply(f"{EMOJI_CROSS} Не найден id в плагине")
            return

        exists, current_status = is_plugin_in_store(metadata.get("id"))

        submission_data = {
            "user_id": message.from_user.id,
            "username": message.from_user.username or "Unknown",
            "temp_path": str(temp_path),
            "plugin_file": message.document.file_name,
            "file_id": message.document.file_id,
            "file_size": getattr(message.document, "file_size", 0),
            "is_elyx": is_elyx,
            "metadata": metadata,
            "dependencies": dependencies,
            "submission_id": message.message_id,
            "exists": exists,
            "status": current_status if exists else None,
        }

        pending_file_data[message.from_user.id] = submission_data

        if is_group or (exists and current_status):
            await _send_to_group(bot, pending_submissions, message.from_user.id)
            if is_private:
                await message.reply(
                    f"{EMOJI_CHECK} Плагин обновлён! Категория: <b>{get_category_label(current_status)}</b>\n"
                    f"Заявка отправлена в группу на рассмотрение.",
                )
        else:
            await message.reply(
                f"{EMOJI_PACKAGE} <b>Плагин:</b> <code>{html.escape(str(metadata.get('id', 'N/A')))}</code>\n"
                f"{EMOJI_MEMO} <b>Название:</b> {html.escape(str(metadata.get('name', 'N/A')))}\n"
                f"{EMOJI_DEVELOPER} <b>Автор:</b> {html.escape(str(metadata.get('author', 'N/A')))}\n"
                f"{EMOJI_PIN} <b>Версия:</b> {html.escape(str(metadata.get('version', 'N/A')))}\n\n"
                f"Выбери категорию плагина:",
                reply_markup=category_keyboard(),
            )

    except Exception as e:
        print(f"Ошибка при обработке плагина: {e}")
        await message.reply(f"{EMOJI_CROSS} Ошибка при обработке файла: {html.escape(str(e))}")
