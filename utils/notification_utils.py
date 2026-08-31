import html
from telebot import types

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


def send_plugin_update_notification(bot, plugin_id, plugin_name, author, version, is_new, status="plugin"):
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

        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
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
        )

        if UPDATES_TOPIC_ID:
            bot.send_message(
                UPDATES_CHAT_ID,
                notification_text,
                parse_mode="HTML",
                message_thread_id=UPDATES_TOPIC_ID,
                reply_markup=keyboard,
            )
        else:
            bot.send_message(
                UPDATES_CHAT_ID,
                notification_text,
                parse_mode="HTML",
                reply_markup=keyboard,
            )

        print(f"✅ Уведомление об обновлении плагина {plugin_id} отправлено в топик")
        return True

    except Exception as e:
        print(f"⚠️ Ошибка при отправке уведомления об обновлении: {e}")
        return False


def send_plugin_delete_notification(bot, plugin_id, reason, admin_user):
    try:
        admin_name = admin_user.username or str(admin_user.id)

        notification_text = (
            f"{EMOJI_TRASH} <b>Плагин удалён</b>\n\n"
            f"{EMOJI_PACKAGE} <b>ID:</b> <code>{html.escape(str(plugin_id))}</code>\n"
            f"{EMOJI_MESSAGES} <b>Причина:</b> {html.escape(reason)}\n"
            f"{EMOJI_USER} <b>Удалил:</b> @{html.escape(admin_name)}"
        )

        if UPDATES_TOPIC_ID:
            bot.send_message(
                UPDATES_CHAT_ID,
                notification_text,
                parse_mode="HTML",
                message_thread_id=UPDATES_TOPIC_ID,
            )
        else:
            bot.send_message(
                UPDATES_CHAT_ID,
                notification_text,
                parse_mode="HTML",
            )

        print(f"✅ Уведомление об удалении плагина {plugin_id} отправлено в топик")
        return True

    except Exception as e:
        print(f"⚠️ Ошибка при отправке уведомления об удалении: {e}")
        return False
