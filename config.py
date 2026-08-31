import os
from pathlib import Path


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

if not os.path.exists(REPO_PATH):
    raise ValueError(
        f"❌ Репозиторий не найден: {REPO_PATH}\n"
        f"   Установите переменную окружения PLUGINS_STORE_PATH или разместите\n"
        f"   Plugins-Store рядом с PluginsBot или в родительских директориях."
    )
if not os.path.exists(PLUGINS_DIR):
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
