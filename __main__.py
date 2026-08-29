import sys
from pathlib import Path

_dir = Path(__file__).resolve().parent
_parent = str(_dir.parent)

if _parent not in sys.path:
    sys.path.insert(0, _parent)

import telebot
from telebot import apihelper

from PluginsBot.config import BOT_TOKEN, REPO_PATH, GROUP_ID
from PluginsBot.handlers import register_command_handlers
from PluginsBot.handlers import register_plugin_handlers
from PluginsBot.handlers import register_approval_handlers

apihelper.CONNECT_TIMEOUT = 500
apihelper.READ_TIMEOUT = 500

bot = telebot.TeleBot(BOT_TOKEN)

pending_submissions = {}

register_command_handlers(bot, pending_submissions)
register_plugin_handlers(bot, pending_submissions)
register_approval_handlers(bot, pending_submissions)


if __name__ == "__main__":
    print("🤖 Бот запущен и готов к работе...")
    print(f"📁 Репозиторий: {REPO_PATH}")
    print(f"👥 Группа для заявок: {GROUP_ID}")
    bot.infinity_polling()
