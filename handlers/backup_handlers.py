import os
import time
import asyncio
from pathlib import Path

from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile

from PluginsBot.config import (
    BACKUP_ENABLED,
    BACKUP_CHAT_ID,
    BACKUP_INTERVAL_HOURS,
    BACKUP_STATE_FILE,
    KEY_BACKUP_PASSWORD,
)
from PluginsBot.utils.backup_utils import build_backup
from PluginsBot.utils.emoji_utils import e, ID_FOLDER, ID_CHECK, ID_WARNING

router = Router()


def _read_last_ts():
    try:
        return float(Path(BACKUP_STATE_FILE).read_text().strip())
    except Exception:
        return 0.0


def _write_last_ts(ts):
    try:
        p = Path(BACKUP_STATE_FILE)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(str(ts))
    except Exception as ex:
        print(f"⚠️ Не удалось сохранить время бэкапа: {ex}")


async def send_backup(bot: Bot, chat_id=None):
    cid = chat_id or BACKUP_CHAT_ID
    if not cid:
        print("⚠️ BACKUP_CHAT_ID не задан — бэкап не отправлен")
        return False

    try:
        info = await asyncio.to_thread(build_backup)
    except Exception as ex:
        print(f"❌ Не удалось собрать бэкап: {ex}")
        return False

    if info["encrypted"]:
        lock = f"{e(ID_CHECK, '🔒')} зашифрован (AES-ZIP, открой 7-Zip по паролю)"
    else:
        lock = f"{e(ID_WARNING, '⚠️')} БЕЗ шифрования"
    names = ", ".join(Path(f).name for f in info["files"])
    caption = (
        f"{e(ID_FOLDER, '🗄')} <b>Бэкап KPM</b>\n"
        f"{lock}\n"
        f"Файлов: {len(info['files'])}\n"
        f"Размер: {info['size']} Б\n"
        f"sha256: <code>{info['sha256']}</code>\n\n"
        f"Содержимое: {names}"
    )

    ok = False
    try:
        doc = FSInputFile(info["path"], filename=info["name"])
        await bot.send_document(cid, doc, caption=caption[:1000])
        _write_last_ts(time.time())
        print(f"✅ Бэкап отправлен в {cid}: {info['name']}")
        ok = True
    except Exception as ex:
        print(f"❌ Не удалось отправить бэкап: {ex}")
    finally:
        try:
            os.unlink(info["path"])
        except Exception:
            pass

    if not info["encrypted"]:
        print("⚠️ Бэкап отправлен без шифрования — задай KEY_BACKUP_PASSWORD!")
    return ok


async def backup_scheduler(bot: Bot):
    while True:
        try:
            interval = max(1.0, float(BACKUP_INTERVAL_HOURS)) * 3600
            if time.time() - _read_last_ts() >= interval:
                await send_backup(bot)
        except Exception as ex:
            print(f"❌ Ошибка планировщика бэкапа: {ex}")
        await asyncio.sleep(600)


@router.message(Command("backup"))
async def handle_backup(message: Message, bot: Bot):
    if BACKUP_CHAT_ID and message.chat.id != BACKUP_CHAT_ID:
        await message.reply(f"{e(ID_WARNING, '⛔')} Команда доступна только владельцу")
        return
    await message.reply(f"{e(ID_FOLDER, '🗄')} Собираю бэкап…")
    ok = await send_backup(bot, message.chat.id)
    if not ok:
        await message.reply(f"{e(ID_WARNING, '❌')} Не удалось отправить бэкап, смотри логи")


def setup_backup_scheduler(bot: Bot):
    if not BACKUP_ENABLED:
        print("🗄 Автобэкап выключен (BACKUP_ENABLED=0)")
        return

    if not BACKUP_CHAT_ID:
        print("⚠️ BACKUP_CHAT_ID не задан — автобэкап выключен (доступна команда /backup в личке)")
        return

    asyncio.create_task(backup_scheduler(bot))
    print(f"🗄 Автобэкап включён: каждые {BACKUP_INTERVAL_HOURS} ч → {BACKUP_CHAT_ID}")
