from telebot import types

from PluginsBot.handlers.command_handlers import CATEGORIES, get_category_label
from PluginsBot.utils.emoji_utils import (
    make_inline_button,
    check_and_update_from_message,
    ID_CHECK,
    ID_CROSS,
    ID_TRASH,
    ID_DOWNLOAD,
    ID_REFRESH,
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
    EMOJI_CLIPBOARD,
    EMOJI_PIN,
    EMOJI_MOBILE,
    EMOJI_MOBILE_ARROW,
    EMOJI_FOLDER,
    EMOJI_FILE,
    EMOJI_LIBRARY_TEXT,
    EMOJI_LINK,
    EMOJI_PLUS,
    EMOJI_REFRESH,
    EMOJI_BACK,
    EMOJI_DOWNLOAD,
    EMOJI_WARNING,
    EMOJI_TOOLS,
    EMOJI_PALETTE,
    EMOJI_INFO,
    EMOJI_GAME,
)


def demo_reply_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📋 Карточка заявки", "✅ Плагин одобрен")
    markup.row("❌ Плагин отклонён", "🗑 Удаление плагина")
    markup.row("📢 Пост в канал", "📊 Статус очереди")
    markup.row("🎨 Все эмодзи")
    return markup


def _get_demo_keyboard(target: str) -> types.InlineKeyboardMarkup | None:
    if target == "card":
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.row(
            make_inline_button("Принять", callback_data="test_msg_dummy", emoji_id=ID_CHECK, fallback_emoji="✅", style="success"),
            make_inline_button("Отклонить", callback_data="test_msg_dummy", emoji_id=ID_CROSS, fallback_emoji="❌", style="danger"),
        )
        for key, (name, fallback, emoji_id) in CATEGORIES.items():
            kb.add(make_inline_button(name, callback_data="test_msg_dummy", emoji_id=emoji_id, fallback_emoji=fallback))
        return kb

    elif target == "delete":
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            make_inline_button("Да, удалить", callback_data="test_msg_dummy", emoji_id=ID_TRASH, fallback_emoji="✅", style="danger"),
            make_inline_button("Отмена", callback_data="test_msg_dummy", emoji_id=ID_CROSS, fallback_emoji="❌"),
        )
        return kb

    elif target == "channel":
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            make_inline_button("Установить", url="tg://kpm_install?plugin=example_plugin", emoji_id=ID_DOWNLOAD, fallback_emoji="⬇️", style="primary"),
            make_inline_button("Обновить список", url="tg://kpm_list", emoji_id=ID_REFRESH, fallback_emoji="🔄"),
        )
        return kb

    return None


def send_demo_message(bot, chat_id, target: str):
    kb = _get_demo_keyboard(target)

    if target == "card":
        text = (
            f"{EMOJI_CLIPBOARD} <b>Новая заявка на плагин</b>\n\n"
            f"{EMOJI_USER} От: @username\n"
            f"{EMOJI_PACKAGE} ID: <code>example_plugin</code>\n"
            f"{EMOJI_MEMO} Название: Example Plugin\n"
            f"{EMOJI_DEVELOPER} Автор: @developer\n"
            f"{EMOJI_PIN} Версия: 1.0.0\n"
            f"{EMOJI_MOBILE} Min version: 1.0.0\n"
            f"{EMOJI_MOBILE_ARROW} App version: 2.0.0\n"
            f"{EMOJI_FOLDER} Категория: <b>{get_category_label('utilities')}</b>\n"
            f"{EMOJI_FILE} Описание: Тестовое описание плагина для проверки отображения эмодзи.\n"
            f"{EMOJI_PACKAGE} Requirements: telebot, requests\n"
            f"{EMOJI_LIBRARY_TEXT} Зависимости: mandre_lib\n"
            f"{EMOJI_LINK} Требует: base_plugin (1.0.0)\n\n"
            f"{EMOJI_FILE} Файл: <code>example_plugin.plugin</code>"
        )
        sent = bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)
        if check_and_update_from_message(sent) is False and kb:
            bot.edit_message_reply_markup(chat_id, sent.message_id, reply_markup=_get_demo_keyboard(target))

    elif target == "approved":
        text = (
            f"{EMOJI_CHECK} <b>Плагин одобрен!</b>\n\n"
            f"Ваш плагин <code>example_plugin</code> успешно добавлен в хранилище.\n"
            f"Коммит: <code>Add plugin: example_plugin v1.0.0</code>"
        )
        sent = bot.send_message(chat_id, text, parse_mode="HTML")
        check_and_update_from_message(sent)

    elif target == "rejected":
        text = (
            f"{EMOJI_CROSS} <b>Плагин отклонён</b>\n\n"
            f"{EMOJI_PACKAGE} ID: <code>example_plugin</code>\n"
            f"{EMOJI_MESSAGES_TEXT} Причина: Ошибки импорта зависимостей\n"
            f"{EMOJI_USER} Отклонил: @admin\n\n"
            f"Если у вас есть вопросы, обратитесь к администраторам."
        )
        sent = bot.send_message(chat_id, text, parse_mode="HTML")
        check_and_update_from_message(sent)

    elif target == "delete":
        text = (
            f"{EMOJI_TRASH} <b>Удаление плагина</b>\n\n"
            f"{EMOJI_PACKAGE} ID: <code>example_plugin</code>\n"
            f"{EMOJI_MEMO} Название: Example Plugin\n"
            f"{EMOJI_DEVELOPER} Автор: @developer\n\n"
            f"Вы уверены?"
        )
        sent = bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)
        if check_and_update_from_message(sent) is False and kb:
            bot.edit_message_reply_markup(chat_id, sent.message_id, reply_markup=_get_demo_keyboard(target))

    elif target == "channel":
        text = (
            f"{EMOJI_PLUS} <b>Новый плагин</b>\n\n"
            f"{EMOJI_PACKAGE} <b>ID:</b> <code>example_plugin</code>\n"
            f"{EMOJI_MEMO} <b>Название:</b> Example Plugin\n"
            f"{EMOJI_DEVELOPER} <b>Автор:</b> @developer\n"
            f"{EMOJI_PIN} <b>Версия:</b> 1.0.0\n"
            f"{EMOJI_FOLDER} <b>Тип:</b> Утилиты"
        )
        sent = bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)
        if check_and_update_from_message(sent) is False and kb:
            bot.edit_message_reply_markup(chat_id, sent.message_id, reply_markup=_get_demo_keyboard(target))

    elif target == "status":
        text = (
            f"{EMOJI_CHART} <b>В очереди 2 заявки:</b>\n\n"
            f"• ID: <code>custom_theme</code> от @user1\n"
            f"• ID: <code>auto_translate</code> от @user2"
        )
        sent = bot.send_message(chat_id, text, parse_mode="HTML")
        check_and_update_from_message(sent)

    elif target == "all_emojis":
        text = (
            f"{EMOJI_PALETTE} <b>Список всех эмодзи бота:</b>\n\n"
            f"• Галочка: {EMOJI_CHECK}\n"
            f"• Крестик: {EMOJI_CROSS}\n"
            f"• Привет: {EMOJI_WAVE}\n"
            f"• Заметка: {EMOJI_MEMO}\n"
            f"• Пакет: {EMOJI_PACKAGE}\n"
            f"• Автор: {EMOJI_DEVELOPER}\n"
            f"• Пин: {EMOJI_PIN}\n"
            f"• Телефон: {EMOJI_MOBILE}\n"
            f"• Телефон со стрелкой: {EMOJI_MOBILE_ARROW}\n"
            f"• Папка: {EMOJI_FOLDER}\n"
            f"• График / Статус: {EMOJI_CHART}\n"
            f"• Документ: {EMOJI_FILE}\n"
            f"• Ссылка: {EMOJI_LINK}\n"
            f"• Пользователь: {EMOJI_USER}\n"
            f"• Предупреждение: {EMOJI_WARNING}\n"
            f"• Корзина: {EMOJI_TRASH}\n"
            f"• Плюс: {EMOJI_PLUS}\n"
            f"• Обновление: {EMOJI_REFRESH}\n"
            f"• Планшет: {EMOJI_CLIPBOARD}\n"
            f"• Назад: {EMOJI_BACK}\n"
            f"• Скачать: {EMOJI_DOWNLOAD}\n"
            f"• Утилиты: {EMOJI_TOOLS}\n"
            f"• Кастомизация: {EMOJI_PALETTE}\n"
            f"• Инфо: {EMOJI_INFO}\n"
            f"• Развлечения: {EMOJI_GAME}\n"
            f"• Чат (текст): {EMOJI_MESSAGES_TEXT}\n"
            f"• Библиотека (текст): {EMOJI_LIBRARY_TEXT}"
        )
        sent = bot.send_message(chat_id, text, parse_mode="HTML")
        check_and_update_from_message(sent)


def register_demo_handlers(bot):
    @bot.message_handler(func=lambda m: m.text == "📋 Карточка заявки")
    def handle_demo_card(message: types.Message):
        send_demo_message(bot, message.chat.id, "card")

    @bot.message_handler(func=lambda m: m.text == "✅ Плагин одобрен")
    def handle_demo_approved(message: types.Message):
        send_demo_message(bot, message.chat.id, "approved")

    @bot.message_handler(func=lambda m: m.text == "❌ Плагин отклонён")
    def handle_demo_rejected(message: types.Message):
        send_demo_message(bot, message.chat.id, "rejected")

    @bot.message_handler(func=lambda m: m.text == "🗑 Удаление плагина")
    def handle_demo_delete(message: types.Message):
        send_demo_message(bot, message.chat.id, "delete")

    @bot.message_handler(func=lambda m: m.text == "📢 Пост в канал")
    def handle_demo_channel(message: types.Message):
        send_demo_message(bot, message.chat.id, "channel")

    @bot.message_handler(func=lambda m: m.text == "📊 Статус очереди")
    def handle_demo_status(message: types.Message):
        send_demo_message(bot, message.chat.id, "status")

    @bot.message_handler(func=lambda m: m.text == "🎨 Все эмодзи")
    def handle_demo_emojis(message: types.Message):
        send_demo_message(bot, message.chat.id, "all_emojis")

    @bot.callback_query_handler(func=lambda call: call.data == "test_msg_dummy")
    def handle_dummy_callback(call: types.CallbackQuery):
        bot.answer_callback_query(call.id, "✅ Тестовая кнопка нажата")
