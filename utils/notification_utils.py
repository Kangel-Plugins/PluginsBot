
import html
from telebot import types

from PluginsBot.config import UPDATES_CHAT_ID, UPDATES_TOPIC_ID


def send_plugin_update_notification(bot, plugin_id, plugin_name, author, version, is_new, status="plugin"):
    try:
        action = "➕ Новый плагин" if is_new else "🔄 Обновление плагина"

        status_labels = {
            "library": "Библиотека",
            "customization": "Кастомизация",
            "utilities": "Утилиты",
            "informational": "Информация",
            "fun": "Развлечения",
            "messages": "Сообщения",
            "plugin": "Плагин"
        }
        type_label = status_labels.get(status.lower(), "Плагин") if status else "Плагин"

        notification_text = (
            f"{action}\n\n"
            f"📦 <b>ID:</b> <code>{html.escape(str(plugin_id))}</code>\n"
            f"📝 <b>Название:</b> {html.escape(str(plugin_name))}\n"
            f"👨‍💻 <b>Автор:</b> {html.escape(str(author))}\n"
            f"📌 <b>Версия:</b> {html.escape(str(version))}\n"
            f"📂 <b>Тип:</b> {html.escape(str(type_label))}"
        )

        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            types.InlineKeyboardButton(
                "⬇️ Установить",
                url=f"tg://kpm_install?plugin={html.escape(str(plugin_id))}"
            ),
            types.InlineKeyboardButton(
                "🔄 Обновить список",
                url="tg://kpm_list"
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

        print(f"✅ Уведомление об обновлении плагина {plugin_id} отправлено")
        return True

    except Exception as e:
        print(f"⚠️ Ошибка при отправке уведомления об обновлении: {e}")
        return False


def send_plugin_delete_notification(bot, plugin_id, reason, admin_user):
    try:
        admin_name = admin_user.username or str(admin_user.id)

        notification_text = (
            f"🗑 <b>Плагин удалён</b>\n\n"
            f"📦 <b>ID:</b> <code>{html.escape(str(plugin_id))}</code>\n"
            f"💬 <b>Причина:</b> {html.escape(reason)}\n"
            f"👤 <b>Удалил:</b> @{html.escape(admin_name)}"
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
