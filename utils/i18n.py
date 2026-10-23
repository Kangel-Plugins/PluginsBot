import json
import os
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Optional

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from PluginsBot.config import USER_LANG_FILE

LOCALES_DIR = Path(__file__).resolve().parent.parent / "locales"
SUPPORTED_LANGS = ("ru", "en", "uk", "zh")
DEFAULT_LANG = "en"
LANG_NAMES = {
    "ru": "Русский",
    "en": "English",
    "uk": "Українська",
    "zh": "中文",
}

_strings: Dict[str, Dict[str, str]] = {}
for _lang in SUPPORTED_LANGS:
    with open(LOCALES_DIR / f"{_lang}.json", "r", encoding="utf-8") as _f:
        _strings[_lang] = json.load(_f)

_user_langs: Optional[Dict[str, str]] = None


def t(key: str, lang: str = DEFAULT_LANG, **kwargs: Any) -> str:
    text = _strings.get(lang, {}).get(key) or _strings[DEFAULT_LANG].get(key) or key
    return text.format(**kwargs) if kwargs else text


def normalize_lang(code: Optional[str]) -> Optional[str]:
    if not code:
        return None
    base = code.lower().replace("_", "-").split("-")[0]
    return base if base in SUPPORTED_LANGS else None


def _read_prefs() -> Dict[str, str]:
    global _user_langs
    if _user_langs is None:
        try:
            with open(USER_LANG_FILE, "r", encoding="utf-8") as f:
                _user_langs = json.load(f)
        except Exception:
            _user_langs = {}
    return _user_langs


def get_user_lang(user_id: int, language_code: Optional[str] = None) -> str:
    stored = _read_prefs().get(str(user_id))
    if stored in SUPPORTED_LANGS:
        return stored
    return normalize_lang(language_code) or DEFAULT_LANG


def set_user_lang(user_id: int, lang: str) -> None:
    if lang not in SUPPORTED_LANGS:
        raise ValueError(f"Unsupported language: {lang}")
    prefs = _read_prefs()
    prefs[str(user_id)] = lang
    try:
        path = Path(USER_LANG_FILE)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(prefs, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)
    except Exception as ex:
        print(f"⚠️ Не удалось сохранить язык пользователя: {ex}")


class LocaleMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user:
            data["lang"] = get_user_lang(user.id, user.language_code)
        else:
            data["lang"] = DEFAULT_LANG
        return await handler(event, data)
