import os
import re
import tempfile
import html
from telebot import types

from PluginsBot.config import GROUP_ID, PLUGINS_DIR, UPDATES_CHAT_ID
from PluginsBot.handlers.command_handlers import CATEGORIES, get_category_label, get_category_name, category_keyboard
from PluginsBot.utils.plugin_utils import extract_plugin_metadata, detect_dependencies, extract_elyx_metadata, is_elyx_plugin
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


pending_file_data = {}


def create_approval_keyboard(submission_id: int, needs_status: bool = False) -> types.InlineKeyboardMarkup:
    keyboard = types.InlineKeyboardMarkup(row_width=2)

    keyboard.row(
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
    )

    if needs_status:
        buttons = [
            make_inline_button(
                text=name,
                callback_data=f"status_{key}_{submission_id}",
                emoji_id=emoji_id,
                fallback_emoji=fallback,
            )
            for key, (name, fallback, emoji_id) in CATEGORIES.items()
        ]
        keyboard.add(*buttons)

    return keyboard


def _send_to_group(bot, pending_submissions, user_id):
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
    if description:
        desc_preview = description[:200] + "..." if len(description) > 200 else description
        info_text += f"{EMOJI_FILE} Описание: {html.escape(desc_preview)}\n"

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

    is_elyx = data.get("is_elyx", False)
    plugin_content = data["plugin_content"]
    tmp_suffix = ".eaf" if is_elyx else ".plugin"
    tmp_file = tempfile.NamedTemporaryFile(suffix=tmp_suffix, delete=False, mode="wb")
    if isinstance(plugin_content, str):
        tmp_file.write(plugin_content.encode("utf-8"))
    else:
        tmp_file.write(plugin_content)
    tmp_file.close()
    tmp_path = tmp_file.name

    try:
        with open(tmp_path, "rb") as plugin_file:
            group_message = bot.send_document(
                GROUP_ID,
                plugin_file,
                caption=info_text,
                parse_mode="HTML",
                reply_markup=create_approval_keyboard(submission_id, needs_status=not data.get('exists')),
            )
            check_and_update_from_message(group_message)
            pending_submissions[submission_id]["group_message_id"] = group_message.message_id
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def register_plugin_handlers(bot, pending_submissions):

    @bot.callback_query_handler(func=lambda call: call.data.startswith("status_"))
    def handle_status_selection(call: types.CallbackQuery):
        data_parts = call.data.split("_")
        new_status = data_parts[1]
        submission_id = int(data_parts[2])

        if submission_id not in pending_submissions:
            bot.answer_callback_query(call.id, "❌ Заявка не найдена", show_alert=True)
            return

        pending_submissions[submission_id]["status"] = new_status
        caption = call.message.caption or ""

        status_pattern = re.compile(r"\n?(?:<tg-emoji[^>]*>)?📊(?:</tg-emoji>)? Выбранный статус: <b>.*?</b>")
        caption = status_pattern.sub("", caption)

        cat_lbl = get_category_label(new_status)
        info_text = caption + f"\n{EMOJI_CHART_TEXT} Выбранный статус: <b>{cat_lbl}</b>"

        bot.edit_message_caption(
            caption=info_text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=create_approval_keyboard(submission_id, needs_status=False)
        )
        bot.answer_callback_query(call.id, f"✅ Статус: {get_category_name(new_status)}")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("cat_"))
    def handle_category_selection(call: types.CallbackQuery):
        user_id = call.from_user.id
        if user_id not in pending_file_data:
            bot.answer_callback_query(call.id, "❌ Файл не найден, отправьте плагин заново", show_alert=True)
            return

        category = call.data[len("cat_"):]
        pending_file_data[user_id]["status"] = category

        _send_to_group(bot, pending_submissions, user_id)

        msg_text = f"{EMOJI_CHECK} Категория: <b>{get_category_label(category)}</b>\n\nЗаявка отправлена в группу на рассмотрение."
        try:
            bot.edit_message_text(
                msg_text,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML",
            )
        except Exception:
            bot.send_message(
                call.message.chat.id,
                msg_text,
                parse_mode="HTML",
            )

        bot.answer_callback_query(call.id, "✅ Заявка отправлена!")

    @bot.message_handler(content_types=["document"])
    def handle_plugin_submission(message: types.Message):
        is_private = message.chat.type == "private"
        is_group = message.chat.id == GROUP_ID
        is_updates = message.chat.id == UPDATES_CHAT_ID

        if is_group or is_updates:
            return

        if not is_private:
            bot.reply_to(
                message,
                f"{EMOJI_CROSS} Отправь плагин мне в личные сообщения (@KPMAppealBot)",
                parse_mode="HTML"
            )
            return

        if is_private:
            try:
                chat_member = bot.get_chat_member(UPDATES_CHAT_ID, message.from_user.id)
                if chat_member.status in ("left", "kicked", "restricted"):
                    bot.reply_to(
                        message,
                        f"{EMOJI_CROSS} Для отправки плагинов необходимо зайти в @KangelPluginsManager",
                        parse_mode="HTML"
                    )
                    return
            except Exception as e:
                print(f"⚠️ Ошибка при проверке членства в чате: {e}")
                bot.reply_to(
                    message,
                    f"{EMOJI_CROSS} Для отправки плагинов необходимо зайти в @KangelPluginsManager",
                    parse_mode="HTML"
                )
                return

        filename = message.document.file_name.lower()
        if not (filename.endswith(".plugin") or filename.endswith(".zip") or filename.endswith(".elyx") or filename.endswith(".eaf")):
            bot.reply_to(message, f"{EMOJI_CROSS} Отправь файл с расширением .plugin, .eaf, .elyx или .zip", parse_mode="HTML")
            return

        try:
            file_info = bot.get_file(message.document.file_id)
            downloaded_file = bot.download_file(file_info.file_path)

            is_elyx = is_elyx_plugin(message.document.file_name)
            if not is_elyx and downloaded_file[:4] == b'PK\x03\x04':
                is_elyx = True

            if is_elyx:
                metadata = extract_elyx_metadata(downloaded_file)
                dependencies = []
                plugin_content = downloaded_file
            else:
                plugin_content = downloaded_file.decode("utf-8", errors="ignore")
                metadata = extract_plugin_metadata(plugin_content)
                dependencies = detect_dependencies(plugin_content)

            if not metadata.get("id"):
                bot.reply_to(message, f"{EMOJI_CROSS} Не найден id в плагине", parse_mode="HTML")
                return

            exists, current_status = is_plugin_in_store(metadata.get("id"))

            pending_file_data[message.from_user.id] = {
                "user_id": message.from_user.id,
                "username": message.from_user.username or "Unknown",
                "plugin_content": plugin_content,
                "plugin_file": message.document.file_name,
                "is_elyx": is_elyx,
                "metadata": metadata,
                "dependencies": dependencies,
                "submission_id": message.message_id,
                "exists": exists,
                "status": current_status if exists else None,
            }

            if exists and current_status:
                _send_to_group(bot, pending_submissions, message.from_user.id)
                bot.reply_to(
                    message,
                    f"{EMOJI_CHECK} Плагин обновлён! Категория: <b>{get_category_label(current_status)}</b>\n"
                    f"Заявка отправлена в группу на рассмотрение.",
                    parse_mode="HTML",
                )
            else:
                bot.reply_to(
                    message,
                    f"{EMOJI_PACKAGE} <b>Плагин:</b> <code>{html.escape(str(metadata.get('id', 'N/A')))}</code>\n"
                    f"{EMOJI_MEMO} <b>Название:</b> {html.escape(str(metadata.get('name', 'N/A')))}\n"
                    f"{EMOJI_DEVELOPER} <b>Автор:</b> {html.escape(str(metadata.get('author', 'N/A')))}\n"
                    f"{EMOJI_PIN} <b>Версия:</b> {html.escape(str(metadata.get('version', 'N/A')))}\n\n"
                    f"Выбери категорию плагина:",
                    parse_mode="HTML",
                    reply_markup=category_keyboard(),
                )

        except Exception as e:
            print(f"Ошибка при обработке плагина: {e}")
            bot.reply_to(message, f"{EMOJI_CROSS} Ошибка при обработке файла: {html.escape(str(e))}", parse_mode="HTML")
