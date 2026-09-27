import os
import math
import asyncio
import logging
import threading
from pathlib import Path
from typing import Optional, Union

from PluginsBot.config import (
    BOT_TOKEN,
    API_ID,
    API_HASH,
    FILE_TRANSFER_CHAT_ID,
    BOT_SESSIONS_DIR,
    PLUGIN_LIMIT,
    ELYX_LIMIT,
    BOT_DOWNLOAD_BYTES,
    GROUP_ID,
)

logger = logging.getLogger(__name__)

ELYX_EXTENSIONS = ("elyx.zip", "eaf.zip", "elyx", "eaf", "zip")


def plugin_extension(filename: Union[str, Path]) -> str:
    name = str(filename).lower()
    for ext in ELYX_EXTENSIONS:
        if name.endswith("." + ext):
            return ext
    if name.endswith(".plugin"):
        return "plugin"
    return ""


def is_elyx_plugin(filename: Union[str, Path]) -> bool:
    name = str(filename).lower()
    return any(name.endswith("." + ext) for ext in ELYX_EXTENSIONS)


def plugin_file_limit(filename: Union[str, Path]) -> int:
    return ELYX_LIMIT if is_elyx_plugin(filename) else PLUGIN_LIMIT


def format_size(bytes_num: int) -> str:
    if bytes_num >= 1024 * 1024 * 1024:
        return f"{bytes_num / (1024 * 1024 * 1024):.1f} ГБ"
    if bytes_num >= 1024 * 1024:
        return f"{bytes_num / (1024 * 1024):.1f} МБ"
    if bytes_num >= 1024:
        return f"{bytes_num / 1024:.1f} КБ"
    return f"{bytes_num} Б"


# --- Fast Background MTProto Bot Client Management ---

_mtproto_loop: Optional[asyncio.AbstractEventLoop] = None
_mtproto_thread: Optional[threading.Thread] = None
_mtproto_client = None
_mtproto_lock = threading.Lock()


def _get_or_create_loop() -> asyncio.AbstractEventLoop:
    global _mtproto_loop, _mtproto_thread
    with _mtproto_lock:
        if _mtproto_loop is None or not _mtproto_loop.is_running():
            _mtproto_loop = asyncio.new_event_loop()
            _mtproto_thread = threading.Thread(
                target=_mtproto_loop.run_forever,
                daemon=True,
                name="MTProtoBotLoop",
            )
            _mtproto_thread.start()
        return _mtproto_loop


async def _async_get_mtproto_client():
    global _mtproto_client
    if not API_ID or not API_HASH:
        raise ValueError("MTProto API_ID и API_HASH не настроены в .env")

    if _mtproto_client is not None:
        try:
            if not _mtproto_client.is_connected():
                await asyncio.wait_for(_mtproto_client.connect(), timeout=15)
            return _mtproto_client
        except Exception:
            _mtproto_client = None

    try:
        from telethon import TelegramClient
    except ImportError:
        raise RuntimeError("Пакет telethon не установлен. Выполните: pip install telethon")

    token = BOT_TOKEN or ""
    bot_id = int(token.split(":", 1)[0]) if ":" in token else 0

    session_dir = Path(BOT_SESSIONS_DIR)
    session_dir.mkdir(parents=True, exist_ok=True)
    session_path = session_dir / f"file_bot_{bot_id}"

    client = TelegramClient(
        str(session_path),
        int(API_ID),
        str(API_HASH),
        receive_updates=False,
    )
    await asyncio.wait_for(client.connect(), timeout=20)

    if not await client.is_user_authorized():
        await asyncio.wait_for(client.sign_in(bot_token=token), timeout=20)

    me = await client.get_me()
    if not me or not getattr(me, "bot", False):
        raise ValueError("Не удалось авторизовать бота через MTProto")

    _mtproto_client = client
    return _mtproto_client


async def _fast_download_document(client, doc, max_workers: int = 8) -> bytes:
    from telethon.tl.functions.upload import GetFileRequest
    from telethon.tl.types import InputDocumentFileLocation

    file_size = doc.size
    part_size = 512 * 1024 
    total_parts = math.ceil(file_size / part_size)

    location = InputDocumentFileLocation(
        id=doc.id,
        access_hash=doc.access_hash,
        file_reference=doc.file_reference,
        thumb_size="",
    )

    parts = [None] * total_parts
    semaphore = asyncio.Semaphore(max_workers)

    async def _fetch_part(part_index: int):
        offset = part_index * part_size
        limit = min(part_size, file_size - offset)
        async with semaphore:
            for attempt in range(3):
                try:
                    res = await client(GetFileRequest(
                        location=location,
                        offset=offset,
                        limit=limit,
                    ))
                    parts[part_index] = res.bytes
                    return
                except Exception:
                    if attempt == 2:
                        raise
                    await asyncio.sleep(0.3)

    tasks = [_fetch_part(i) for i in range(total_parts)]
    await asyncio.gather(*tasks)
    return b"".join(parts)


async def _async_download_large_file(bot, file_id: str, max_size: int = ELYX_LIMIT) -> bytes:
    client = await _async_get_mtproto_client()
    transfer_chat = FILE_TRANSFER_CHAT_ID or GROUP_ID

    try:
        entity = await client.get_entity(transfer_chat)
    except Exception:
        try:
            chat = bot.get_chat(transfer_chat)
            if chat.username:
                entity = await client.get_entity(chat.username)
            else:
                from telethon.tl.types import InputChannel
                channel_id = abs(int(transfer_chat))
                if channel_id > 1000000000000:
                    channel_id -= 1000000000000
                entity = await client.get_entity(InputChannel(channel_id, 0))
        except Exception:
            entity = await client.get_input_entity(int(transfer_chat))

    staging_msg = None
    try:
        staging_msg = bot.send_document(
            transfer_chat,
            file_id,
            disable_notification=True,
        )
        source = await client.get_messages(entity, ids=staging_msg.message_id)
        if not source or not source.document:
            raise ValueError("Не удалось получить документ через MTProto")

        if source.document.size > max_size:
            raise ValueError(f"Размер файла превышает лимит ({format_size(max_size)})")

        try:
            data = await asyncio.wait_for(
                _fast_download_document(client, source.document, max_workers=8),
                timeout=180,
            )
        except Exception as exc:
            logger.warning(f"Fast parallel download failed ({exc}), falling back to standard download...")
            data = await asyncio.wait_for(
                client.download_media(source, file=bytes),
                timeout=300,
            )

        if not data:
            raise ValueError("Ошибка при скачивании файла через MTProto")
        return data

    finally:
        if staging_msg:
            try:
                bot.delete_message(transfer_chat, staging_msg.message_id)
            except Exception:
                pass


def download_plugin_file(bot, document) -> bytes:

    file_name = document.file_name or "plugin.plugin"
    file_size = getattr(document, "file_size", 0) or 0
    max_limit = plugin_file_limit(file_name)

    if file_size > max_limit:
        raise ValueError(
            f"Размер файла ({format_size(file_size)}) превышает лимит: "
            f"{'8 МБ для .plugin' if not is_elyx_plugin(file_name) else '100 МБ для Elyx (.elyx/.eaf/.zip)'}"
        )
    if file_size and file_size <= BOT_DOWNLOAD_BYTES:
        try:
            file_info = bot.get_file(document.file_id)
            return bot.download_file(file_info.file_path)
        except Exception as exc:
            err_str = str(exc).lower()
            if "file is too big" not in err_str and "400" not in err_str:
                if not (API_ID and API_HASH):
                    raise
            logger.warning(f"Bot API download failed ({exc}), falling back to fast MTProto...")


    if not (API_ID and API_HASH):
        raise ValueError(
            f"Файл больше 20 МБ ({format_size(file_size)}). "
            f"Для быстрой загрузки файлов до 100 МБ укажите API_ID и API_HASH в .env"
        )

    loop = _get_or_create_loop()
    future = asyncio.run_coroutine_threadsafe(
        _async_download_large_file(bot, document.file_id, max_limit),
        loop,
    )
    return future.result(timeout=240)
