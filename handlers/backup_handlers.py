import os
import time
import threading
from pathlib import Path

from telebot import types

from PluginsBot.config import (
    BACKUP_ENABLED,
    BACKUP_CHAT_ID,
    BACKUP_INTERVAL_HOURS,
    BACKUP_STATE_FILE,
    KEY_BACKUP_PASSWORD,
)
from PluginsBot.utils.backup_utils import build_backup
from PluginsBot.utils.emoji_utils import e, ID_FOLDER, ID_CHECK, ID_WARNING


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
    except Exception as e:
        print(f"⚠️ Не удалось сохранить время бэкапа: {e}")


def send_backup(bot, chat_id=None):
    cid = chat_id or BACKUP_CHAT_ID
    if not cid:
        print("⚠️ BACKUP_CHAT_ID не задан — бэкап не отправлен")
        return False

    try:
        info = build_backup()
    except Exception as e:
        print(f"❌ Не удалось собрать бэкап: {e}")
        return False

    lock = f"{e(ID_CHECK, '🔒')} зашифрован паролем" if info["encrypted"] else f"{e(ID_WARNING, '⚠️')} БЕЗ шифрования"
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
        with open(info["path"], "rb") as f:
            bot.send_document(cid, f, caption=caption[:1000], parse_mode="HTML")
        _write_last_ts(time.time())
        print(f"✅ Бэкап отправлен в {cid}: {info['name']}")
        ok = True
    except Exception as e:
        print(f"❌ Не удалось отправить бэкап: {e}")
    finally:
        try:
            os.unlink(info["path"])
        except Exception:
            pass

    if not info["encrypted"]:
        print("⚠️ Бэкап отправлен без шифрования — задай KEY_BACKUP_PASSWORD!")
    return ok


def _scheduler(bot):
    while True:
        try:
            interval = max(1.0, float(BACKUP_INTERVAL_HOURS)) * 3600
            if time.time() - _read_last_ts() >= interval:
                send_backup(bot)
        except Exception as e:
            print(f"❌ Ошибка планировщика бэкапа: {e}")
        time.sleep(600)


def register_backup_handlers(bot):
    @bot.message_handler(commands=["backup"])
    def handle_backup(message: types.Message):
        if BACKUP_CHAT_ID and message.chat.id != BACKUP_CHAT_ID:
            bot.reply_to(message, f"{e(ID_WARNING, '⛔')} Команда доступна только владельцу", parse_mode="HTML")
            return
        bot.reply_to(message, f"{e(ID_FOLDER, '🗄')} Собираю бэкап…", parse_mode="HTML")
        ok = send_backup(bot, message.chat.id)
        if not ok:
            bot.reply_to(message, f"{e(ID_WARNING, '❌')} Не удалось отправить бэкап, смотри логи", parse_mode="HTML")

    if not BACKUP_ENABLED:
        print("🗄 Автобэкап выключен (BACKUP_ENABLED=0)")
        return

    if not BACKUP_CHAT_ID:
        print("⚠️ BACKUP_CHAT_ID не задан — автобэкап выключен (доступна команда /backup в личке)")
        return

    threading.Thread(target=_scheduler, args=(bot,), daemon=True).start()
    print(f"🗄 Автобэкап включён: каждые {BACKUP_INTERVAL_HOURS} ч → {BACKUP_CHAT_ID}")
