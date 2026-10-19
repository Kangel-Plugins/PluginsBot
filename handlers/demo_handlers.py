import html
import re
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
)

from PluginsBot.handlers.command_handlers import (
    CATEGORIES,
    get_category_label,
    get_category_name,
)
from PluginsBot.utils.emoji_utils import (
    make_inline_button,
    check_and_update_from_message,
    ID_CHECK,
    ID_CROSS,
    ID_TRASH,
    ID_DOWNLOAD,
    ID_REFRESH,
    ID_BACK,
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
    EMOJI_CHART_TEXT,
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

router = Router()

demo_rejections: dict[int | str, dict | int] = {}


def _get_admin_display(user) -> str:
    if getattr(user, "username", None):
        return f"@{user.username}"
    first = getattr(user, "first_name", "") or ""
    last = getattr(user, "last_name", "") or ""
    full = f"{first} {last}".strip()
    return full if full else f"ID {user.id}"


def demo_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Карточка заявки"), KeyboardButton(text="✅ Плагин одобрен")],
            [KeyboardButton(text="❌ Плагин отклонён"), KeyboardButton(text="🗑 Удаление плагина")],
            [KeyboardButton(text="📢 Пост в канал"), KeyboardButton(text="📊 Статус очереди")],
            [KeyboardButton(text="🎨 Все эмодзи")],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def _get_demo_card_keyboard(needs_status: bool = True) -> InlineKeyboardMarkup:
    buttons = [
        [
            make_inline_button("Принять", callback_data="demo_approve", emoji_id=ID_CHECK, fallback_emoji="✅", style="success"),
            make_inline_button("Отклонить", callback_data="demo_reject", emoji_id=ID_CROSS, fallback_emoji="❌", style="danger"),
        ]
    ]

    if needs_status:
        cat_buttons = []
        for key, (name, fallback, emoji_id) in CATEGORIES.items():
            cat_buttons.append(
                make_inline_button(name, callback_data=f"demo_cat_{key}", emoji_id=emoji_id, fallback_emoji=fallback)
            )
            if len(cat_buttons) == 2:
                buttons.append(cat_buttons)
                cat_buttons = []
        if cat_buttons:
            buttons.append(cat_buttons)

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _get_demo_rejection_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                make_inline_button(
                    "Назад",
                    callback_data="demo_rejx",
                    emoji_id=ID_BACK,
                    fallback_emoji="◀️",
                ),
                make_inline_button(
                    "Да, отклонить (без причины)",
                    callback_data="demo_rejc",
                    emoji_id=ID_CROSS,
                    fallback_emoji="❌",
                    style="danger",
                ),
            ]
        ]
    )


def _get_demo_delete_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                make_inline_button(
                    "Да, удалить",
                    callback_data="demo_delp",
                    emoji_id=ID_TRASH,
                    fallback_emoji="✅",
                    style="danger",
                ),
                make_inline_button(
                    "Отмена",
                    callback_data="demo_delx",
                    emoji_id=ID_CROSS,
                    fallback_emoji="❌",
                ),
            ]
        ]
    )


def _get_demo_channel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                make_inline_button("Установить", url="tg://kpm_install?plugin=example_plugin", emoji_id=ID_DOWNLOAD, fallback_emoji="⬇️", style="primary"),
                make_inline_button("Обновить список", url="tg://kpm_list", emoji_id=ID_REFRESH, fallback_emoji="🔄"),
            ]
        ]
    )


def _get_demo_keyboard(target: str) -> InlineKeyboardMarkup | None:
    if target == "card":
        return _get_demo_card_keyboard(needs_status=True)
    elif target == "delete":
        return _get_demo_delete_keyboard()
    elif target == "channel":
        return _get_demo_channel_keyboard()
    return None


def _build_demo_card_text(selected_status_key: str | None = None) -> str:
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
        f"{EMOJI_FILE} Описание:\n"
        f"<blockquote expandable>Это подробное расширенное описание плагина для проверки и демонстрации работы свёрнутой цитаты в Telegram.\n\n"
        f"Основные возможности и функции:\n"
        f"• Автоматическая синхронизация настроек и конфигурационных файлов между сессиями.\n"
        f"• Поддержка кастомных тем оформления, шрифтов и цветовых палитр интерфейса.\n"
        f"• Встроенный менеджер быстрых действий и горячих клавиш для ускорения работы.\n"
        f"• Интеграция с внешними API, облачными сервисами и локальными базами данных.\n"
        f"• Детальное логирование событий, экспорт отчётов и встроенная система самодиагностики.\n\n"
        f"Для работы требуются установленные зависимости и актуальная версия приложения. "
        f"Нажмите на блок цитаты, чтобы развернуть или свернуть полный текст описания.</blockquote>\n"
        f"{EMOJI_PACKAGE} Requirements: telebot, requests\n"
        f"{EMOJI_LIBRARY_TEXT} Зависимости: mandre_lib\n"
        f"{EMOJI_LINK} Требует: base_plugin (1.0.0)\n\n"
        f"{EMOJI_FILE} Файл: <code>example_plugin.plugin</code>"
    )
    if selected_status_key:
        cat_lbl = get_category_label(selected_status_key)
        text += f"\n{EMOJI_CHART_TEXT} Выбранный статус: <b>{cat_lbl}</b>"
    return text


async def send_demo_message(bot: Bot, chat_id: int, target: str):
    kb = _get_demo_keyboard(target)

    if target == "card":
        text = _build_demo_card_text()
        sent = await bot.send_message(chat_id, text, reply_markup=kb)
        if check_and_update_from_message(sent) is False and kb:
            try:
                await bot.edit_message_reply_markup(chat_id=chat_id, message_id=sent.message_id, reply_markup=_get_demo_keyboard(target))
            except Exception:
                pass

    elif target == "approved":
        text = (
            f"{EMOJI_CHECK} <b>Плагин одобрен!</b>\n\n"
            f"Ваш плагин <code>example_plugin</code> успешно добавлен в хранилище.\n"
            f"Коммит: <code>Add plugin: example_plugin v1.0.0</code>"
        )
        sent = await bot.send_message(chat_id, text)
        check_and_update_from_message(sent)

    elif target == "rejected":
        text = (
            f"{EMOJI_CROSS} <b>Плагин отклонён</b>\n\n"
            f"{EMOJI_PACKAGE} ID: <code>example_plugin</code>\n"
            f"{EMOJI_MESSAGES_TEXT} Причина: Ошибки импорта зависимостей\n"
            f"{EMOJI_USER} Отклонил: @admin\n\n"
            f"Если у вас есть вопросы, обратитесь к администраторам."
        )
        sent = await bot.send_message(chat_id, text)
        check_and_update_from_message(sent)

    elif target == "delete":
        text = (
            f"{EMOJI_TRASH} <b>Удаление плагина</b>\n\n"
            f"{EMOJI_PACKAGE} ID: <code>example_plugin</code>\n"
            f"{EMOJI_MEMO} Название: Example Plugin\n"
            f"{EMOJI_DEVELOPER} Автор: @developer\n\n"
            f"Вы уверены?"
        )
        sent = await bot.send_message(chat_id, text, reply_markup=kb)
        if check_and_update_from_message(sent) is False and kb:
            try:
                await bot.edit_message_reply_markup(chat_id=chat_id, message_id=sent.message_id, reply_markup=_get_demo_keyboard(target))
            except Exception:
                pass

    elif target == "channel":
        text = (
            f"{EMOJI_PLUS} <b>Новый плагин</b>\n\n"
            f"{EMOJI_PACKAGE} <b>ID:</b> <code>example_plugin</code>\n"
            f"{EMOJI_MEMO} <b>Название:</b> Example Plugin\n"
            f"{EMOJI_DEVELOPER} <b>Автор:</b> @developer\n"
            f"{EMOJI_PIN} <b>Версия:</b> 1.0.0\n"
            f"{EMOJI_FOLDER} <b>Тип:</b> {get_category_label('utilities')}\n\n"
            f"<blockquote expandable>Это подробное расширенное описание плагина для проверки и демонстрации работы свёрнутой цитаты в Telegram.\n\n"
            f"Основные возможности и функции:\n"
            f"• Автоматическая синхронизация настроек и конфигурационных файлов между сессиями.\n"
            f"• Поддержка кастомных тем оформления, шрифтов и цветовых палитр интерфейса.\n"
            f"• Встроенный менеджер быстрых действий и горячих клавиш для ускорения работы.\n"
            f"• Интеграция с внешними API, облачными сервисами и локальными базами данных.\n"
            f"• Детальное логирование событий, экспорт отчётов и встроенная система самодиагностики.\n\n"
            f"Для работы требуются установленные зависимости и актуальная версия приложения. "
            f"Нажмите на блок цитаты, чтобы развернуть или свернуть полный текст описания.</blockquote>"
        )
        sent = await bot.send_message(chat_id, text, reply_markup=kb)
        if check_and_update_from_message(sent) is False and kb:
            try:
                await bot.edit_message_reply_markup(chat_id=chat_id, message_id=sent.message_id, reply_markup=_get_demo_keyboard(target))
            except Exception:
                pass

    elif target == "status":
        text = (
            f"{EMOJI_CHART} <b>В очереди 2 заявки:</b>\n\n"
            f"• ID: <code>custom_theme</code> от @user1\n"
            f"• ID: <code>auto_translate</code> от @user2"
        )
        sent = await bot.send_message(chat_id, text)
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
        sent = await bot.send_message(chat_id, text)
        check_and_update_from_message(sent)


@router.message(Command("demo"))
async def handle_demo_command(message: Message):
    sent = await message.reply(
        f"{EMOJI_TOOLS} <b>Панель демо-режима</b>\n\nВыберите действие на клавиатуре ниже:",
        reply_markup=demo_reply_keyboard(),
    )
    check_and_update_from_message(sent)


@router.message(F.text.contains("Карточка заявки"))
async def handle_demo_card(message: Message, bot: Bot):
    await send_demo_message(bot, message.chat.id, "card")


@router.message(F.text.contains("Плагин одобрен"))
async def handle_demo_approved(message: Message, bot: Bot):
    await send_demo_message(bot, message.chat.id, "approved")


@router.message(F.text.contains("Плагин отклонён"))
async def handle_demo_rejected(message: Message, bot: Bot):
    await send_demo_message(bot, message.chat.id, "rejected")


@router.message(F.text.contains("Удаление плагина"))
async def handle_demo_delete(message: Message, bot: Bot):
    await send_demo_message(bot, message.chat.id, "delete")


@router.message(F.text.contains("Пост в канал"))
async def handle_demo_channel(message: Message, bot: Bot):
    await send_demo_message(bot, message.chat.id, "channel")


@router.message(F.text.contains("Статус очереди"))
async def handle_demo_status(message: Message, bot: Bot):
    await send_demo_message(bot, message.chat.id, "status")


@router.message(F.text.contains("Все эмодзи"))
async def handle_demo_emojis(message: Message, bot: Bot):
    await send_demo_message(bot, message.chat.id, "all_emojis")


# =========================================================================
# Interactive Callbacks for Demo Mode
# =========================================================================

@router.callback_query(F.data.startswith("demo_cat_"))
async def handle_demo_status_selection(call: CallbackQuery):
    cat_key = call.data[len("demo_cat_"):]
    cat_name = get_category_name(cat_key)

    new_text = _build_demo_card_text(selected_status_key=cat_key)

    kb = _get_demo_card_keyboard(needs_status=False)
    try:
        if call.message.caption:
            await call.message.edit_caption(caption=new_text, reply_markup=kb)
        else:
            await call.message.edit_text(text=new_text, reply_markup=kb)
    except Exception:
        pass

    await call.answer(f"✅ Статус: {cat_name}")


@router.callback_query(F.data == "demo_approve")
async def handle_demo_approve(call: CallbackQuery, bot: Bot):
    await call.answer("✅ Плагин успешно добавлен!", show_alert=True)

    demo_rejections.pop(call.message.message_id, None)
    demo_rejections.pop(f"card_{call.message.message_id}", None)

    try:
        await call.message.delete()
    except Exception:
        pass

    author_text = (
        f"{EMOJI_CHECK} <b>Плагин одобрен! (демо)</b>\n\n"
        f"Ваш плагин <code>example_plugin</code> успешно добавлен в хранилище.\n"
        f"Коммит: <code>Add plugin: example_plugin v1.0.0</code>"
    )
    sent_author = await bot.send_message(call.message.chat.id, author_text)
    check_and_update_from_message(sent_author)

    await send_demo_message(bot, call.message.chat.id, "channel")


@router.callback_query(F.data == "demo_reject")
async def handle_demo_reject(call: CallbackQuery, bot: Bot):
    kb = _get_demo_rejection_keyboard()

    rejection_text = (
        f"{EMOJI_CROSS} <b>Отклонение плагина (демо)</b>\n\n"
        f"{EMOJI_PACKAGE} ID: <code>example_plugin</code>\n"
        f"{EMOJI_MEMO} Название: Example Plugin\n"
        f"{EMOJI_DEVELOPER} Автор: @developer\n\n"
        f"Введите причину отказа следующим сообщением в чат или подтвердите кнопкой."
    )

    try:
        if call.message.caption:
            await call.message.edit_caption(caption=rejection_text, reply_markup=kb)
        else:
            await call.message.edit_text(text=rejection_text, reply_markup=kb)
    except Exception:
        await call.message.edit_reply_markup(reply_markup=kb)

    rejection_info = {
        "card_message_id": call.message.message_id,
        "chat_id": call.message.chat.id,
        "admin_user": call.from_user,
    }

    demo_rejections[call.message.message_id] = rejection_info

    await call.answer("Введите причину отказа сообщением в чат или подтвердите")


@router.callback_query(F.data == "demo_rejc")
async def handle_demo_reject_confirm(call: CallbackQuery, bot: Bot):
    card_msg_id = call.message.message_id
    demo_rejections.pop(card_msg_id, None)

    try:
        await call.message.delete()
    except Exception:
        pass

    admin_display = _get_admin_display(call.from_user)

    author_text = (
        f"{EMOJI_CROSS} <b>Плагин отклонён (демо)</b>\n\n"
        f"{EMOJI_PACKAGE} ID: <code>example_plugin</code>\n"
        f"{EMOJI_MESSAGES_TEXT} Причина: Причина не указана\n"
        f"{EMOJI_USER} Отклонил: {html.escape(admin_display)}\n\n"
        f"Если у вас есть вопросы, обратитесь к администраторам."
    )
    sent_author = await bot.send_message(call.message.chat.id, author_text)
    check_and_update_from_message(sent_author)

    group_text = (
        f"{EMOJI_CROSS} <b>Отклонено</b>: <code>example_plugin</code>\n"
        f"{EMOJI_MESSAGES_TEXT} Причина: Причина не указана\n"
        f"{EMOJI_USER} Отклонил: {html.escape(admin_display)}"
    )
    sent_group = await bot.send_message(call.message.chat.id, group_text)
    check_and_update_from_message(sent_group)

    await call.answer("✅ Плагин отклонён")


@router.callback_query(F.data == "demo_rejx")
async def handle_demo_reject_cancel(call: CallbackQuery, bot: Bot):
    card_msg_id = call.message.message_id
    demo_rejections.pop(card_msg_id, None)

    original_text = _build_demo_card_text()
    kb = _get_demo_card_keyboard(needs_status=True)

    try:
        if call.message.caption:
            await call.message.edit_caption(caption=original_text, reply_markup=kb)
        else:
            await call.message.edit_text(text=original_text, reply_markup=kb)
    except Exception:
        await call.message.edit_reply_markup(reply_markup=kb)

    await call.answer("Отменено")


def _find_demo_rejection(message: Message) -> dict | None:
    if not message.text or message.text.startswith("/"):
        return None

    # 1. Если ответили напрямую на карточку
    if message.reply_to_message:
        reply_id = message.reply_to_message.message_id
        info = demo_rejections.get(reply_id)
        if info and isinstance(info, dict):
            initiator = info.get("admin_user")
            if initiator and message.from_user.id != initiator.id:
                return None
            return info

    # 2. Обычное сообщение в чате от инициатора
    for k, v in demo_rejections.items():
        if isinstance(v, dict) and v.get("chat_id") == message.chat.id:
            initiator = v.get("admin_user")
            if initiator and initiator.id == message.from_user.id:
                return v

    return None


def _is_demo_rejection_message(message: Message) -> bool:
    return _find_demo_rejection(message) is not None


@router.message(_is_demo_rejection_message)
async def handle_demo_reject_reply(message: Message, bot: Bot):
    info = _find_demo_rejection(message)
    if not info or not isinstance(info, dict):
        return

    initiator = info.get("admin_user")
    card_msg_id = info.get("card_message_id")
    if card_msg_id:
        demo_rejections.pop(card_msg_id, None)

    reason = message.text.strip() or "Причина не указана"

    try:
        await message.delete()
    except Exception:
        pass

    if card_msg_id:
        try:
            await bot.delete_message(message.chat.id, card_msg_id)
        except Exception:
            pass

    admin_display = _get_admin_display(initiator or message.from_user)

    author_text = (
        f"{EMOJI_CROSS} <b>Плагин отклонён (демо)</b>\n\n"
        f"{EMOJI_PACKAGE} ID: <code>example_plugin</code>\n"
        f"{EMOJI_MESSAGES_TEXT} Причина: {html.escape(reason)}\n"
        f"{EMOJI_USER} Отклонил: {html.escape(admin_display)}\n\n"
        f"Если у вас есть вопросы, обратитесь к администраторам."
    )
    sent_author = await bot.send_message(message.chat.id, author_text)
    check_and_update_from_message(sent_author)

    group_text = (
        f"{EMOJI_CROSS} <b>Отклонено</b>: <code>example_plugin</code>\n"
        f"{EMOJI_MESSAGES_TEXT} Причина: {html.escape(reason)}\n"
        f"{EMOJI_USER} Отклонил: {html.escape(admin_display)}"
    )
    sent_group = await bot.send_message(message.chat.id, group_text)
    check_and_update_from_message(sent_group)


@router.callback_query(F.data == "demo_delp")
async def handle_demo_delete_confirm(call: CallbackQuery, bot: Bot):
    await call.answer("Удаляю...")
    try:
        await call.message.delete()
    except Exception:
        pass

    admin_display = _get_admin_display(call.from_user)

    channel_text = (
        f"{EMOJI_TRASH} <b>Плагин удалён из магазина</b>\n\n"
        f"{EMOJI_PACKAGE} <b>ID:</b> <code>example_plugin</code>\n"
        f"{EMOJI_MEMO} <b>Название:</b> Example Plugin\n"
        f"{EMOJI_DEVELOPER} <b>Автор:</b> @developer\n"
        f"{EMOJI_MESSAGES_TEXT} <b>Причина:</b> Причина не указана\n"
        f"{EMOJI_USER} <b>Модератор:</b> {html.escape(admin_display)}"
    )
    sent_channel = await bot.send_message(call.message.chat.id, channel_text)
    check_and_update_from_message(sent_channel)

    dm_text = (
        f"{EMOJI_TRASH} <b>Плагин удалён (демо)</b>\n\n"
        f"{EMOJI_PACKAGE} ID: <code>example_plugin</code>\n"
        f"{EMOJI_MESSAGES_TEXT} Причина: Причина не указана\n"
        f"{EMOJI_USER} Удалил: {html.escape(admin_display)}"
    )
    sent_dm = await bot.send_message(call.message.chat.id, dm_text)
    check_and_update_from_message(sent_dm)


@router.callback_query(F.data == "demo_delx")
async def handle_demo_delete_cancel(call: CallbackQuery):
    await call.answer("Отменено")
    try:
        await call.message.delete()
    except Exception:
        pass


@router.callback_query(F.data == "test_msg_dummy")
async def handle_dummy_callback(call: CallbackQuery):
    await call.answer("✅ Тестовая кнопка нажата")
