import sys
import asyncio
from pathlib import Path

_dir = Path(__file__).resolve().parent
_parent = str(_dir.parent)

if _parent not in sys.path:
    sys.path.insert(0, _parent)

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from PluginsBot.config import BOT_TOKEN, REPO_PATH, GROUP_ID, IS_DEMO
from PluginsBot.handlers import (
    command_router,
    plugin_router,
    approval_router,
    demo_router,
    backup_router,
    setup_backup_scheduler,
)


async def main():
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    pending_submissions = {}
    dp["pending_submissions"] = pending_submissions

    dp.include_router(command_router)
    dp.include_router(plugin_router)
    dp.include_router(approval_router)
    dp.include_router(backup_router)

    if IS_DEMO:
        dp.include_router(demo_router)

    setup_backup_scheduler(bot)

    print("🤖 Бот запущен и готов к работе (aiogram 3)...")
    if IS_DEMO:
        print("🧪 Включен режим DEMO (--demo). Доступна клавиатура тестирования всех сообщений.")
    print(f"📁 Репозиторий: {REPO_PATH}")
    print(f"👥 Группа для заявок: {GROUP_ID}")

    await dp.start_polling(bot)


def run():
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("🛑 Бот остановлен")


if __name__ == "__main__":
    run()
