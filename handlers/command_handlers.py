import re
import html
from telebot import types

from PluginsBot.config import GROUP_ID, UPDATES_CHAT_ID, IS_DEMO
from PluginsBot.utils.emoji_utils import (
    e,
    make_inline_button,
    check_and_update_from_message,
    ID_CHECK,
    ID_CROSS,
    ID_TOOLS,
    ID_PALETTE,
    ID_INFO,
    ID_GAME,
    ID_MESSAGES,
    ID_LIBRARY,
    ID_TRASH,
    EMOJI_CROSS,
    EMOJI_CHECK,
    EMOJI_WAVE,
    EMOJI_MEMO,
    EMOJI_PACKAGE,
    EMOJI_DEVELOPER,
    EMOJI_TRASH,
    EMOJI_MESSAGES_TEXT,
    EMOJI_USER,
    EMOJI_CHART,
)


CATEGORIES = {
    "utilities": ("Утилиты", "🛠", ID_TOOLS),
    "customization": ("Кастомизация", "🎨", ID_PALETTE),
    "informational": ("Инфо", "ℹ️", ID_INFO),
    "fun": ("Развлечения", "🎮", ID_GAME),
    "messages": ("Сообщения", "💬", ID_MESSAGES),
    "library": ("Библиотека", "📚", ID_LIBRARY),
}


def get_category_label(key: str) -> str:
    if key in CATEGORIES:
        name, fallback, emoji_id = CATEGORIES[key]
        return f"{e(emoji_id, fallback)} {name}"
    return key


def get_category_name(key: str) -> str:
    if key in CATEGORIES:
        return CATEGORIES[key][0]
    return key


def category_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        make_inline_button(
            text=name,
            callback_data=f"cat_{key}",
            emoji_id=emoji_id,
            fallback_emoji=fallback,
        )
        for key, (name, fallback, emoji_id) in CATEGORIES.items()
    ]
    keyboard.add(*buttons)
    return keyboard


def register_command_handlers(bot, pending_submissions):

    @bot.message_handler(commands=["start"])
    def handle_start(message: types.Message):
        if message.chat.type == "private":
            reply_markup = None
            if IS_DEMO:
                from PluginsBot.handlers.demo_handlers import demo_reply_keyboard
                reply_markup = demo_reply_keyboard()

            sent = bot.reply_to(
                message,
                f"{EMOJI_WAVE} Привет! Я бот для управления плагинами.\n\n"
                f"Отправь мне файл плагина (.plugin / .eaf), и я помогу добавить его в хранилище.\n\n"
                f"{EMOJI_MEMO} <b>Плагин должен содержать:</b>\n"
                f"• __id__ = \"plugin_id\"\n"
                f"• __name__ = \"Название\"\n"
                f"• __version__ = \"1.0.0\"\n"
                f"• __author__ = \"@username\"\n\n"
                f"Зависимости детектируются автоматически по импортам.",
                parse_mode="HTML",
                reply_markup=reply_markup,
            )
            check_and_update_from_message(sent)

    @bot.message_handler(commands=["status"])
    def handle_status(message: types.Message):
        if message.chat.id != GROUP_ID:
            bot.reply_to(message, f"{EMOJI_CROSS} Команда доступна только в группе", parse_mode="HTML")
            return

        if not pending_submissions:
            bot.reply_to(message, f"{EMOJI_CHECK} Очередь пуста", parse_mode="HTML")
            return

        status_text = f"{EMOJI_CHART} <b>В очереди {len(pending_submissions)} заявок:</b>\n\n"
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
                f"{EMOJI_CROSS} Использование: /delete <code>plugin_id</code> [причина]",
                parse_mode="HTML",
            )
            return

        args = parts[1].strip().split(maxsplit=1)
        plugin_id = args[0]
        reason = args[1] if len(args) > 1 else None

        from PluginsBot.utils.store_utils import get_plugin_entry
        entry = get_plugin_entry(plugin_id)
        if not entry:
            bot.reply_to(message, f"{EMOJI_CROSS} Плагин <code>{html.escape(plugin_id)}</code> не найден в store.json", parse_mode="HTML")
            return

        if reason:
            _execute_delete(bot, plugin_id, reason, message.from_user)
            return

        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            make_inline_button("Да, удалить", callback_data=f"delp_{plugin_id}", emoji_id=ID_TRASH, fallback_emoji="✅", style="danger"),
            make_inline_button("Отмена", callback_data=f"delx_{plugin_id}", emoji_id=ID_CROSS, fallback_emoji="❌"),
        )

        sent = bot.reply_to(
            message,
            f"{EMOJI_TRASH} <b>Удаление плагина</b>\n\n"
            f"{EMOJI_PACKAGE} ID: <code>{html.escape(plugin_id)}</code>\n"
            f"{EMOJI_MEMO} Название: {html.escape(str(entry.get('name', 'N/A')))}\n"
            f"{EMOJI_DEVELOPER} Автор: {html.escape(str(entry.get('author', 'N/A')))}\n\n"
            f"Вы уверены?",
            parse_mode="HTML",
            reply_markup=keyboard,
        )
        check_and_update_from_message(sent)


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
            f"{EMOJI_TRASH} <b>Плагин удалён</b>\n\n"
            f"{EMOJI_PACKAGE} ID: <code>{html.escape(plugin_id)}</code>\n"
            f"{EMOJI_MESSAGES_TEXT} Причина: {html.escape(reason)}\n"
            f"{EMOJI_USER} Удалил: @{html.escape(admin_name)}",
            parse_mode="HTML",
        )
    except Exception:
        pass

    return True
