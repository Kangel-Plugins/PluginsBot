import os
import sys
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

IS_DEMO = "--demo" in sys.argv or os.getenv("BOT_DEMO", "").lower() in ("1", "true", "yes")

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✅ Загружен .env файл: {env_path}")
except ImportError:
    pass

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError(
        "❌ BOT_TOKEN не установлен! Установите переменную окружения:\n"
        "   export BOT_TOKEN='your_bot_token_here'\n"
        "   или создайте .env файл с BOT_TOKEN=..."
    )

GROUP_ID = int(os.getenv("GROUP_ID", "-1003243078083"))
UPDATES_CHAT_ID = int(os.getenv("UPDATES_CHAT_ID", "-1002977846884"))
UPDATES_TOPIC_ID = int(os.getenv("UPDATES_TOPIC_ID", "1270"))

KPM_FORUM_URL = os.getenv("KPM_FORUM_URL", "https://t.me/KangelPluginsManager")

STORE_RAW_URL = os.getenv(
    "STORE_RAW_URL",
    "https://git.kangel.xyz/KangelPlugins/Plugins-Store/raw/branch/main",
)

def find_plugins_store() -> Path:
    env_path = os.getenv("PLUGINS_STORE_PATH")
    if env_path and os.path.exists(env_path):
        return Path(env_path).resolve()

    bot_plugins_dir = Path(__file__).parent.resolve()

    candidate = bot_plugins_dir / "Plugins-Store"
    if candidate.exists():
        return candidate.resolve()

    candidate = bot_plugins_dir.parent / "Plugins-Store"
    if candidate.exists():
        return candidate.resolve()

    current = bot_plugins_dir
    for _ in range(3):
        current = current.parent
        candidate = current / "Plugins-Store"
        if candidate.exists():
            return candidate.resolve()

    return bot_plugins_dir / "Plugins-Store"


REPO_PATH_OBJ = find_plugins_store()
REPO_PATH = str(REPO_PATH_OBJ)
PLUGINS_DIR = str(REPO_PATH_OBJ / "Plugins")
STORE_JSON_FILE = str(REPO_PATH_OBJ / "store.json")

if not os.path.exists(REPO_PATH) and not IS_DEMO:
    raise ValueError(
        f"❌ Репозиторий не найден: {REPO_PATH}\n"
        f"   Установите переменную окружения PLUGINS_STORE_PATH или разместите\n"
        f"   Plugins-Store рядом с PluginsBot или в родительских директориях."
    )
if not os.path.exists(PLUGINS_DIR) and not IS_DEMO:
    raise ValueError(f"❌ Папка плагинов не найдена: {PLUGINS_DIR}")

if os.getenv("BOT_DEBUG"):
    print(f"📁 Найден Plugins-Store: {REPO_PATH}")

KNOWN_LIBS = {
    "mandre_lib": "mandre_lib",
    "quantahut": "quantahut",
    "zwylib": "zwylib",
    "cactuslib": "cactuslib",
    "dont65_lib": "dont65_lib",
}

PRIVATE_KEY_PATH = os.getenv("PRIVATE_KEY_PATH", os.path.join(REPO_PATH, "private_key.pem"))

BACKUP_ENABLED = str(os.getenv("BACKUP_ENABLED", "1")).lower() in ("1", "true", "yes", "on")
BACKUP_CHAT_ID = int(os.getenv("BACKUP_CHAT_ID") or os.getenv("OWNER_ID") or "0")
BACKUP_INTERVAL_HOURS = float(os.getenv("BACKUP_INTERVAL_HOURS", "24"))
KEY_BACKUP_PASSWORD = os.getenv("KEY_BACKUP_PASSWORD", "")
BACKUP_STATE_FILE = os.getenv("BACKUP_STATE_FILE", str(Path(__file__).parent / "data" / "backup_last.txt"))
USER_LANG_FILE = os.getenv("USER_LANG_FILE", str(Path(__file__).parent / "data" / "user_langs.json"))

API_ID = int(os.getenv("API_ID") or os.getenv("TELEGRAM_API_ID") or "0")
API_HASH = os.getenv("API_HASH") or os.getenv("TELEGRAM_API_HASH") or ""
FILE_TRANSFER_CHAT_ID = int(os.getenv("FILE_TRANSFER_CHAT_ID") or os.getenv("TRANSFER_CHAT_ID") or str(GROUP_ID))
BOT_SESSIONS_DIR = os.getenv("BOT_SESSIONS_DIR", str(Path(__file__).parent / "data" / "bot_sessions"))

PLUGIN_LIMIT = 8 * 1024 * 1024
ELYX_LIMIT = 100 * 1024 * 1024
BOT_DOWNLOAD_BYTES = 20 * 1024 * 1024
