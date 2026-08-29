import re
import html
from telebot import types

from PluginsBot.config import GROUP_ID, UPDATES_CHAT_ID


CATEGORIES = {
    "utilities": "🛠 Утилиты",
    "customization": "🎨 Кастомизация",
    "informational": "ℹ️ Инфо",
    "fun": "🎮 Развлечения",
    "messages": "💬 Сообщения",
    "library": "📚 Библиотека",
}


def category_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        types.InlineKeyboardButton(label, callback_data=f"cat_{key}")
        for key, label in CATEGORIES.items()
    ]
    keyboard.add(*buttons)
    return keyboard


def register_command_handlers(bot, pending_submissions):

    @bot.message_handler(commands=["start"])
    def handle_start(message: types.Message):
        if message.chat.type == "private":
            bot.reply_to(
                message,
                "👋 Привет! Я бот для управления плагинами.\n\n"
                "Отправь мне файл плагина (.plugin / .eaf), и я помогу добавить его в хранилище.\n\n"
                "📝 Плагин должен содержать:\n"
                "• __id__ = \"plugin_id\"\n"
                "• __name__ = \"Название\"\n"
                "• __version__ = \"1.0.0\"\n"
                "• __author__ = \"@username\"\n\n"
                "Зависимости детектируются автоматически по импортам.",
            )

    @bot.message_handler(commands=["status"])
    def handle_status(message: types.Message):
        if message.chat.id != GROUP_ID:
            bot.reply_to(message, "❌ Команда доступна только в группе")
            return

        if not pending_submissions:
            bot.reply_to(message, "✅ Очередь пуста")
            return

        status_text = f"📊 В очереди {len(pending_submissions)} заявок:\n\n"
        for sub_id, sub in pending_submissions.items():
            status_text += (
                f"• ID: <code>{sub['metadata'].get('id')}</code> "
                f"от @{sub['username']}\n"
            )

        bot.reply_to(message, status_text, parse_mode="HTML")

    @bot.message_handler(
        func=lambda m: m.chat.id == GROUP_ID and m.text and m.text.startswith("/delete"),
    )
    def handle_delete(message: types.Message):
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(
                message,
                "❌ Использование: /delete <code>plugin_id</code> [причина]",
                parse_mode="HTML",
            )
            return

        args = parts[1].strip().split(maxsplit=1)
        plugin_id = args[0]
        reason = args[1] if len(args) > 1 else None

        from PluginsBot.utils.store_utils import get_plugin_entry
        entry = get_plugin_entry(plugin_id)
        if not entry:
            bot.reply_to(message, f"❌ Плагин <code>{html.escape(plugin_id)}</code> не найден в store.json", parse_mode="HTML")
            return

        if reason:
            _execute_delete(bot, plugin_id, reason, message.from_user)
            return

        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            types.InlineKeyboardButton("✅ Да, удалить", callback_data=f"delp_{plugin_id}"),
            types.InlineKeyboardButton("❌ Отмена", callback_data=f"delx_{plugin_id}"),
        )

        bot.reply_to(
            message,
            f"🗑 Удаление плагина\n\n"
            f"📦 ID: <code>{html.escape(plugin_id)}</code>\n"
            f"📝 Название: {html.escape(str(entry.get('name', 'N/A')))}\n"
            f"👨‍💻 Автор: {html.escape(str(entry.get('author', 'N/A')))}\n\n"
            f"Вы уверены?",
            parse_mode="HTML",
            reply_markup=keyboard,
        )


def _execute_delete(bot, plugin_id, reason, admin_user):
    import os
    import json
    import shutil
    from PluginsBot.config import PLUGINS_DIR, REPO_PATH, STORE_JSON_FILE
    from PluginsBot.utils.store_utils import get_plugin_filename_by_id
    from PluginsBot.utils.git_utils import commit_and_push
    from PluginsBot.utils.notification_utils import send_plugin_delete_notification

    LEGACY_DIR = os.path.join(REPO_PATH, "legacy_versions")

    filename = get_plugin_filename_by_id(plugin_id)
    if filename:
        plugin_path = os.path.join(PLUGINS_DIR, filename)
        if os.path.exists(plugin_path):
            os.remove(plugin_path)

    legacy_dir = os.path.join(LEGACY_DIR, plugin_id)
    if os.path.isdir(legacy_dir):
        shutil.rmtree(legacy_dir)

    with open(STORE_JSON_FILE, "r", encoding="utf-8") as f:
        store_data = json.load(f)

    if plugin_id in store_data:
        del store_data[plugin_id]

    with open(STORE_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(store_data, f, indent=4, ensure_ascii=False)

    success, msg = commit_and_push(plugin_id, "deleted", False)

    send_plugin_delete_notification(bot, plugin_id, reason, admin_user)

    admin_name = admin_user.username or str(admin_user.id)
    try:
        bot.send_message(
            admin_user.id,
            f"🗑 <b>Плагин удалён</b>\n\n"
            f"📦 ID: <code>{html.escape(plugin_id)}</code>\n"
            f"💬 Причина: {html.escape(reason)}\n"
            f"👤 Удалил: @{html.escape(admin_name)}",
            parse_mode="HTML",
        )
    except Exception:
        pass

    return True
