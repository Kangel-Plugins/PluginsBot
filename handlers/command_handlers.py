import html
import asyncio
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup

from PluginsBot.config import GROUP_ID, IS_DEMO
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
    ID_PACKAGE,
    ID_MEMO,
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
    EMOJI_INFO,
)

router = Router()

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


def category_keyboard() -> InlineKeyboardMarkup:
    rows = []
    current_row = []
    for key, (name, fallback, emoji_id) in CATEGORIES.items():
        btn = make_inline_button(
            text=name,
            callback_data=f"cat_{key}",
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


@router.message(Command("start"))
async def handle_start(message: Message):
    if message.chat.type == "private":
        if IS_DEMO:
            from PluginsBot.handlers.demo_handlers import demo_reply_keyboard
            reply_markup = demo_reply_keyboard()
        else:
            from aiogram.types import ReplyKeyboardRemove
            reply_markup = ReplyKeyboardRemove()

        sent = await message.reply(
            f"{EMOJI_WAVE} <b>Привет! Я бот для управления плагинами.</b>\n\n"
            f"Отправь мне файл плагина, и я помогу добавить его в репозиторий.\n\n"
            f"{EMOJI_PACKAGE} <b>Поддерживаемые форматы:</b>\n"
            f"• Python плагины: <code>.plugin</code> (до 8 МБ)\n"
            f"• Elyx архивы: <code>.elyx</code>, <code>.eaf</code>, <code>.zip</code> (до 100 МБ)\n\n"
            f"{EMOJI_MEMO} <b>Метаданные плагина:</b>\n"
            f"• <code>__id__</code> = <code>\"plugin_id\"</code> (или <code>id</code> в Elyx)\n"
            f"• <code>__name__</code> = <code>\"Название\"</code>\n"
            f"• <code>__version__</code> = <code>\"1.0.0\"</code>\n"
            f"• <code>__author__</code> = <code>\"@username\"</code>\n"
            f"• <code>__description__</code> = <code>\"Описание плагина\"</code>\n"
            f"• <code>__app_version__</code> = <code>\"&gt;=12.5.1\"</code>\n"
            f"• <code>__requirements__</code> = <code>\"requests, PyYAML\"</code> (опционально)\n\n"
            f"Зависимости и метаданные определяются автоматически.",
            reply_markup=reply_markup,
        )
        check_and_update_from_message(sent)


@router.message(Command("status"))
async def handle_status(message: Message, pending_submissions: dict):
    if message.chat.id != GROUP_ID:
        await message.reply(f"{EMOJI_CROSS} Команда доступна только в группе")
        return

    if not pending_submissions:
        await message.reply(f"{EMOJI_CHECK} Очередь пуста")
        return

    status_text = f"{EMOJI_CHART} <b>В очереди {len(pending_submissions)} заявок:</b>\n\n"
    for sub_id, sub in pending_submissions.items():
        status_text += (
            f"• ID: <code>{sub['metadata'].get('id')}</code> "
            f"от @{sub['username']}\n"
        )

    await message.reply(status_text)


@router.message(F.chat.id == GROUP_ID, F.text.startswith("/delete"))
async def handle_delete(message: Message, bot: Bot):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply(f"{EMOJI_CROSS} Использование: /delete <code>plugin_id</code> [причина]")
        return

    args = parts[1].strip().split(maxsplit=1)
    plugin_id = args[0]
    reason = args[1] if len(args) > 1 else None

    from PluginsBot.utils.store_utils import get_plugin_entry
    entry = get_plugin_entry(plugin_id)
    if not entry:
        await message.reply(f"{EMOJI_CROSS} Плагин <code>{html.escape(plugin_id)}</code> не найден в store.json")
        return

    if reason:
        await _execute_delete(bot, plugin_id, reason, message.from_user)
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                make_inline_button("Да, удалить", callback_data=f"delp_{plugin_id}", emoji_id=ID_TRASH, fallback_emoji="✅", style="danger"),
                make_inline_button("Отмена", callback_data=f"delx_{plugin_id}", emoji_id=ID_CROSS, fallback_emoji="❌"),
            ]
        ]
    )

    sent = await message.reply(
        f"{EMOJI_TRASH} <b>Удаление плагина</b>\n\n"
        f"{EMOJI_PACKAGE} ID: <code>{html.escape(plugin_id)}</code>\n"
        f"{EMOJI_MEMO} Название: {html.escape(str(entry.get('name', 'N/A')))}\n"
        f"{EMOJI_DEVELOPER} Автор: {html.escape(str(entry.get('author', 'N/A')))}\n\n"
        f"Вы уверены?",
        reply_markup=keyboard,
    )
    check_and_update_from_message(sent)


@router.callback_query(F.data.startswith("delp_"))
async def handle_delete_confirm(call: CallbackQuery, bot: Bot):
    if call.message.chat.id != GROUP_ID:
        await call.answer("❌ Команда доступна только в группе", show_alert=True)
        return

    plugin_id = call.data[len("delp_"):]
    await call.answer("Удаляю...")
    try:
        await call.message.delete()
    except Exception:
        pass

    await _execute_delete(bot, plugin_id, "Причина не указана", call.from_user)


@router.callback_query(F.data.startswith("delx_"))
async def handle_delete_cancel(call: CallbackQuery):
    if call.message.chat.id != GROUP_ID:
        await call.answer("❌ Команда доступна только в группе", show_alert=True)
        return

    await call.answer("Отменено")
    try:
        await call.message.delete()
    except Exception:
        pass


async def _execute_delete(bot: Bot, plugin_id: str, reason: str, admin_user):
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

    await asyncio.to_thread(commit_and_push, plugin_id, "deleted", False)

    await send_plugin_delete_notification(bot, plugin_id, reason, admin_user)

    admin_name = getattr(admin_user, "username", None) or str(getattr(admin_user, "id", "Unknown"))
    try:
        await bot.send_message(
            chat_id=admin_user.id,
            text=(
                f"{EMOJI_TRASH} <b>Плагин удалён</b>\n\n"
                f"{EMOJI_PACKAGE} ID: <code>{html.escape(plugin_id)}</code>\n"
                f"{EMOJI_MESSAGES_TEXT} Причина: {html.escape(reason)}\n"
                f"{EMOJI_USER} Удалил: @{html.escape(admin_name)}"
            ),
        )
    except Exception:
        pass

    return True
