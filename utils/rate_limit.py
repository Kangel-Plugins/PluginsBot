import os
import json
import time
import math
from pathlib import Path
from typing import Tuple, Dict, List
from aiogram import Bot

try:
    from PluginsBot.config import (
        GROUP_ID,
        BACKUP_CHAT_ID,
        RATE_LIMIT_WINDOW,
        SUBMISSION_RATE_LIMIT,
        RATE_LIMITS_FILE,
    )
    from PluginsBot.utils.emoji_utils import EMOJI_CROSS
except ImportError:
    from config import (
        GROUP_ID,
        BACKUP_CHAT_ID,
        RATE_LIMIT_WINDOW,
        SUBMISSION_RATE_LIMIT,
        RATE_LIMITS_FILE,
    )
    from utils.emoji_utils import EMOJI_CROSS

_data: Dict[str, List[float]] = {}
_loaded = False
_admin_cache: Dict[int, Tuple[bool, float]] = {}


def _plural(n: int, one: str, few: str, many: str) -> str:
    n_abs = abs(n) % 100
    n1 = n_abs % 10
    if 11 <= n_abs <= 19:
        return many
    if 2 <= n1 <= 4:
        return few
    if n1 == 1:
        return one
    return many


def plural_submissions(n: int) -> str:
    return _plural(n, 'заявка', 'заявки', 'заявок')


def plural_hours(n: int) -> str:
    return _plural(n, 'час', 'часа', 'часов')


def plural_minutes(n: int) -> str:
    return _plural(n, 'минута', 'минуты', 'минут')


def plural_seconds(n: int) -> str:
    return _plural(n, 'секунда', 'секунды', 'секунд')


def format_window_name(seconds: int) -> str:
    if seconds == 1800:
        return 'полчаса'
    if seconds == 3600:
        return 'час'
    if seconds % 3600 == 0:
        h = seconds // 3600
        return f'{h} {plural_hours(h)}'
    if seconds % 60 == 0:
        m = seconds // 60
        return f'{m} {plural_minutes(m)}'
    return f'{seconds} {plural_seconds(seconds)}'


def format_time_duration(seconds: float) -> str:
    s = int(math.ceil(seconds))
    if s <= 0:
        return 'прямо сейчас'
    if s < 60:
        return f'{s} {plural_seconds(s)}'
    m = s // 60
    sec = s % 60
    if m < 60:
        if sec > 0:
            return f'{m} мин. {sec} сек.'
        return f'{m} {plural_minutes(m)}'
    h = m // 60
    min_rem = m % 60
    if min_rem > 0:
        return f'{h} ч. {min_rem} мин.'
    return f'{h} {plural_hours(h)}'


def _ensure_loaded():
    global _loaded
    if _loaded:
        return
    _loaded = True
    _data.clear()
    if os.path.exists(RATE_LIMITS_FILE):
        try:
            with open(RATE_LIMITS_FILE, 'r', encoding='utf-8') as f:
                content = json.load(f)
                if isinstance(content, dict):
                    if 'users' in content and isinstance(content['users'], dict):
                        for uid, val in content['users'].items():
                            if isinstance(val, dict) and 'submissions' in val:
                                _data[str(uid)] = [float(t) for t in val.get('submissions', [])]
                    else:
                        for uid, val in content.items():
                            if isinstance(val, list):
                                _data[str(uid)] = [float(t) for t in val]
                            elif isinstance(val, dict) and 'submissions' in val:
                                _data[str(uid)] = [float(t) for t in val.get('submissions', [])]
        except Exception as e:
            print(f'⚠️ Ошибка чтения файла лимитов {RATE_LIMITS_FILE}: {e}')


def _save_data():
    _ensure_loaded()
    try:
        file_path = Path(RATE_LIMITS_FILE)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        temp_file = file_path.with_suffix('.tmp')
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(_data, f, ensure_ascii=False)
        os.replace(temp_file, file_path)
    except Exception as e:
        print(f'⚠️ Ошибка сохранения файла лимитов {RATE_LIMITS_FILE}: {e}')


async def is_review_group_admin(bot: Bot, user_id: int) -> bool:
    if BACKUP_CHAT_ID and user_id == BACKUP_CHAT_ID:
        return True

    now = time.time()
    if user_id in _admin_cache:
        is_adm, exp = _admin_cache[user_id]
        if now < exp:
            return is_adm

    try:
        member = await bot.get_chat_member(chat_id=GROUP_ID, user_id=user_id)
        is_adm = member.status in ('creator', 'administrator', 'member')
        _admin_cache[user_id] = (is_adm, now + 300)
        return is_adm
    except Exception:
        _admin_cache[user_id] = (False, now + 60)
        return False


async def check_rate_limit(
    bot: Bot,
    user_id: int,
) -> Tuple[bool, int, float, int]:
    _ensure_loaded()
    user_str = str(user_id)
    now = time.time()
    window = RATE_LIMIT_WINDOW
    limit = SUBMISSION_RATE_LIMIT

    history = _data.get(user_str, [])
    active = [t for t in history if now - t < window]
    _data[user_str] = active

    if len(active) >= limit:
        oldest = min(active)
        retry_after = max(0.0, (oldest + window) - now)
        return True, limit, retry_after, len(active)

    return False, limit, 0.0, len(active)


def record_submission(user_id: int):
    _ensure_loaded()
    user_str = str(user_id)
    now = time.time()
    window = RATE_LIMIT_WINDOW

    history = _data.get(user_str, [])
    active = [t for t in history if now - t < window * 2]
    active.append(now)
    _data[user_str] = active
    _save_data()


def reset_user_limit(user_id: int) -> bool:
    _ensure_loaded()
    user_str = str(user_id)
    if user_str in _data:
        _data[user_str] = []
        _save_data()
        return True
    return False


def format_rate_limit_error(user_limit: int, retry_after_seconds: float) -> str:
    window_name = format_window_name(RATE_LIMIT_WINDOW)
    time_str = format_time_duration(retry_after_seconds)
    sub_str = plural_submissions(user_limit)
    sep = chr(10)
    lines = [
        f"{EMOJI_CROSS} <b>Превышен лимит заявок!</b>",
        "",
        f"Можно отправить не более <b>{user_limit} {sub_str} в {window_name}</b>.",
        f"Следующую заявку можно отправить через <b>{time_str}</b>."
    ]
    return sep.join(lines)
