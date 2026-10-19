import html
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup

from PluginsBot.config import UPDATES_CHAT_ID, UPDATES_TOPIC_ID
from PluginsBot.utils.emoji_utils import (
    make_inline_button,
    ID_DOWNLOAD,
    ID_REFRESH,
    EMOJI_PLUS,
    EMOJI_REFRESH,
    EMOJI_PACKAGE,
    EMOJI_MEMO,
    EMOJI_DEVELOPER,
    EMOJI_PIN,
    EMOJI_FOLDER,
    EMOJI_TRASH,
    EMOJI_MESSAGES,
    EMOJI_USER,
)


async def send_plugin_update_notification(
    bot: Bot,
    plugin_id: str,
    plugin_name: str,
    author: str,
    version: str,
    is_new: bool,
    status: str = "plugin",
    description: str | None = None,
):
    try:
        action = f"{EMOJI_PLUS} <b>Новый плагин</b>" if is_new else f"{EMOJI_REFRESH} <b>Обновление плагина</b>"

        from PluginsBot.handlers.command_handlers import get_category_label
        type_label = get_category_label(status.lower()) if status else "Плагин"

        notification_text = (
            f"{action}\n\n"
            f"{EMOJI_PACKAGE} <b>ID:</b> <code>{html.escape(str(plugin_id))}</code>\n"
            f"{EMOJI_MEMO} <b>Название:</b> {html.escape(str(plugin_name))}\n"
            f"{EMOJI_DEVELOPER} <b>Автор:</b> {html.escape(str(author))}\n"
            f"{EMOJI_PIN} <b>Версия:</b> {html.escape(str(version))}\n"
            f"{EMOJI_FOLDER} <b>Тип:</b> {type_label}"
        )

        if description and str(description).strip():
            desc_clean = str(description).replace("\\n", "\n").strip()
            if len(desc_clean) > 3000:
                desc_clean = desc_clean[:2997] + "..."
            notification_text += f"\n\n<blockquote expandable>{html.escape(desc_clean)}</blockquote>"

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    make_inline_button(
                        "Установить",
                        url=f"tg://kpm_install?plugin={html.escape(str(plugin_id))}",
                        emoji_id=ID_DOWNLOAD,
                        fallback_emoji="⬇️",
                        style="primary",
                    ),
                    make_inline_button(
                        "Обновить список",
                        url="tg://kpm_list",
                        emoji_id=ID_REFRESH,
                        fallback_emoji="🔄",
                    ),
                ]
            ]
        )

        kwargs = {}
        if UPDATES_TOPIC_ID:
            kwargs["message_thread_id"] = UPDATES_TOPIC_ID

        await bot.send_message(
            chat_id=UPDATES_CHAT_ID,
            text=notification_text,
            reply_markup=keyboard,
            **kwargs,
        )

        print(f"✅ Уведомление об обновлении плагина {plugin_id} отправлено в топик")
        return True

    except Exception as e:
        print(f"⚠️ Ошибка при отправке уведомления об обновлении: {e}")
        return False


async def send_plugin_delete_notification(bot: Bot, plugin_id: str, reason: str, admin_user):
    try:
        admin_name = getattr(admin_user, "username", None) or str(getattr(admin_user, "id", "Unknown"))

        notification_text = (
            f"{EMOJI_TRASH} <b>Плагин удалён</b>\n\n"
            f"{EMOJI_PACKAGE} <b>ID:</b> <code>{html.escape(str(plugin_id))}</code>\n"
            f"{EMOJI_MESSAGES} <b>Причина:</b> {html.escape(reason)}\n"
            f"{EMOJI_USER} <b>Удалил:</b> @{html.escape(admin_name)}"
        )

        kwargs = {}
        if UPDATES_TOPIC_ID:
            kwargs["message_thread_id"] = UPDATES_TOPIC_ID

        await bot.send_message(
            chat_id=UPDATES_CHAT_ID,
            text=notification_text,
            **kwargs,
        )

        print(f"✅ Уведомление об удалении плагина {plugin_id} отправлено в топик")
        return True

    except Exception as e:
        print(f"⚠️ Ошибка при отправке уведомления об удалении: {e}")
        return False
