
import os
import re
import tempfile
import html
from telebot import types

from PluginsBot.config import GROUP_ID, PLUGINS_DIR, UPDATES_CHAT_ID
from PluginsBot.handlers.command_handlers import CATEGORIES, category_keyboard
from PluginsBot.utils.plugin_utils import extract_plugin_metadata, detect_dependencies, extract_elyx_metadata, is_elyx_plugin
from PluginsBot.utils.store_utils import is_plugin_in_store


pending_file_data = {}


def create_approval_keyboard(submission_id: int, needs_status: bool = False) -> types.InlineKeyboardMarkup:
    keyboard = types.InlineKeyboardMarkup(row_width=2)

    keyboard.row(
        types.InlineKeyboardButton("✅ Принять", callback_data=f"approve_{submission_id}"),
        types.InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{submission_id}"),
    )

    if needs_status:
        buttons = [
            types.InlineKeyboardButton(label, callback_data=f"status_{key}_{submission_id}")
            for key, label in CATEGORIES.items()
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
        f"📋 <b>{'Обновление' if data.get('exists') else 'Новая заявка'} на плагин</b>\n\n"
        f"👤 От: @{data.get('username', 'Unknown')}\n"
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

    if category:
        label = CATEGORIES.get(category, category)
        info_text += f"📂 Категория: <b>{html.escape(label)}</b>\n"

    if data.get('exists'):
        info_text += f"📊 Текущий статус: <b>{html.escape(str(category))}</b>\n"

    description = metadata.get('description')
    if description:
        desc_preview = description[:200] + "..." if len(description) > 200 else description
        info_text += f"📄 Описание: {html.escape(desc_preview)}\n"

    requirements = metadata.get('requirements')
    if requirements:
        safe_reqs = [html.escape(str(r)) for r in requirements]
        info_text += f"📦 Requirements: {', '.join(safe_reqs)}\n"

    dependencies = data.get("dependencies", [])
    if dependencies:
        safe_deps = [html.escape(str(d)) for d in dependencies]
        info_text += f"📚 Зависимости: {', '.join(safe_deps)}\n"

    requires = metadata.get('requires')
    if requires:
        req_texts = []
        for r in requires:
            rlabel = str(r.get('id', '?'))
            ver = r.get('min_version')
            if ver:
                rlabel += f" ({html.escape(str(ver))})"
            req_texts.append(html.escape(rlabel))
        info_text += f"🔗 Требует: {', '.join(req_texts)}\n"

    info_text += f"\n📄 Файл: <code>{html.escape(data.get('plugin_file', 'N/A'))}</code>"

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
        metadata = pending_submissions[submission_id]["metadata"]
        caption = call.message.caption or ""

        status_pattern = re.compile(r"\n?📊 Выбранный статус: <b>.*?</b>")
        caption = status_pattern.sub("", caption)

        label = CATEGORIES.get(new_status, new_status)
        info_text = html.escape(caption) + f"\n📊 Выбранный статус: <b>{html.escape(label)}</b>"

        bot.edit_message_caption(
            caption=info_text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=create_approval_keyboard(submission_id, needs_status=False)
        )
        bot.answer_callback_query(call.id, f"✅ Статус: {label}")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("cat_"))
    def handle_category_selection(call: types.CallbackQuery):
        user_id = call.from_user.id
        if user_id not in pending_file_data:
            bot.answer_callback_query(call.id, "❌ Файл не найден, отправьте плагин заново", show_alert=True)
            return

        category = call.data[len("cat_"):]
        pending_file_data[user_id]["status"] = category

        _send_to_group(bot, pending_submissions, user_id)

        label = CATEGORIES.get(category, category)
        try:
            bot.edit_message_text(
                f"✅ Категория: <b>{label}</b>\n\nЗаявка отправлена в группу на рассмотрение.",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML",
            )
        except Exception:
            bot.send_message(
                call.message.chat.id,
                f"✅ Категория: <b>{label}</b>\n\nЗаявка отправлена в группу на рассмотрение.",
                parse_mode="HTML",
            )

        bot.answer_callback_query(call.id, "✅ Заявка отправлена!")

    @bot.message_handler(content_types=["document"])
    def handle_plugin_submission(message: types.Message):
        is_private = message.chat.type == "private"
        is_group = message.chat.id == GROUP_ID

        if is_group:
            return

        if not is_private:
            bot.reply_to(
                message,
                "❌ Отправь плагин мне в личные сообщения (@KangelPluginsBot)"
            )
            return

        if is_private:
            try:
                chat_member = bot.get_chat_member(UPDATES_CHAT_ID, message.from_user.id)
                if chat_member.status in ("left", "kicked", "restricted"):
                    bot.reply_to(
                        message,
                        "❌ Для отправки плагинов необходимо зайти в @KangelPluginsManager",
                    )
                    return
            except Exception as e:
                print(f"⚠️ Ошибка при проверке членства в чате: {e}")
                bot.reply_to(
                    message,
                    "❌ Для отправки плагинов необходимо зайти в @KangelPluginsManager",
                )
                return

        filename = message.document.file_name.lower()
        if not (filename.endswith(".plugin") or filename.endswith(".zip") or filename.endswith(".elyx") or filename.endswith(".eaf")):
            bot.reply_to(message, "❌ Отправь файл с расширением .plugin, .eaf, .elyx или .zip")
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
                bot.reply_to(message, "❌ Не найден id в плагине")
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
                label = CATEGORIES.get(current_status, current_status)
                bot.reply_to(
                    message,
                    f"✅ Плагин обновлён! Категория: <b>{html.escape(label)}</b>\n"
                    f"Заявка отправлена в группу на рассмотрение.",
                    parse_mode="HTML",
                )
            else:
                bot.reply_to(
                    message,
                    f"📦 Плагин: <code>{html.escape(str(metadata.get('id', 'N/A')))}</code>\n"
                    f"📝 Название: {html.escape(str(metadata.get('name', 'N/A')))}\n"
                    f"👨‍💻 Автор: {html.escape(str(metadata.get('author', 'N/A')))}\n"
                    f"📌 Версия: {html.escape(str(metadata.get('version', 'N/A')))}\n\n"
                    f"Выбери категорию плагина:",
                    parse_mode="HTML",
                    reply_markup=category_keyboard(),
                )

        except Exception as e:
            print(f"Ошибка при обработке плагина: {e}")
            bot.reply_to(message, f"❌ Ошибка при обработке файла: {str(e)}")
