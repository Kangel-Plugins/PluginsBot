import html
import os
from typing import Dict, Optional, Tuple

import aiohttp
from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQuery,
    InlineQueryResultArticle,
    InputMediaDocument,
    InputTextMessageContent,
)

from PluginsBot.config import KPM_FORUM_URL, STORE_JSON_FILE
from PluginsBot.utils.i18n import t
from PluginsBot.utils.store_utils import get_localized_description, get_plugin_entry, search_store

router = Router()

PAGE_SIZE = 20
DESCRIPTION_LIMIT = 1000
CAPTION_DESCRIPTION_LIMIT = 500
MAX_VERSION_BUTTONS = 8
GET_PREFIX = "kpmget:"
PICK_PREFIX = "kpmpick:"
BACK_PREFIX = "kpmback:"
TELEGRAM_UPLOAD_LIMIT = 50 * 1024 * 1024


def _card_text(plugin_id: str, entry: Dict, lang: str, desc_limit: int = DESCRIPTION_LIMIT) -> str:
    name = str(entry.get("name") or plugin_id)
    version = str(entry.get("version") or "N/A")
    author = str(entry.get("author") or "N/A")
    is_library = entry.get("status") == "library"
    type_label = t("inline.type_library" if is_library else "inline.type_plugin", lang)
    description = get_localized_description(entry, lang)

    lines = [
        f"<b>{html.escape(name)}</b>",
        f"{t('label.id', lang)} <code>{html.escape(plugin_id)}</code>",
        f"{t('label.author', lang)} {html.escape(author)}",
        f"{t('label.version', lang)} {html.escape(version)}",
        f"{t('label.type', lang)} {type_label}",
    ]
    min_version = entry.get("min_version")
    if min_version:
        lines.append(f"{t('label.min_version', lang)} {html.escape(str(min_version))}")

    if description:
        desc_clean = description.replace("\\n", "\n")
        if len(desc_clean) > desc_limit:
            desc_clean = desc_clean[:desc_limit - 3] + "..."
        lines.append(f"\n<blockquote expandable>{html.escape(desc_clean)}</blockquote>")

    return "\n".join(lines)


def _callback(prefix: str, plugin_id: str, version: str = "") -> Optional[str]:
    data = f"{prefix}{plugin_id}:{version}"
    return data if len(data.encode()) <= 64 else None


def _keyboard(plugin_id: str, lang: str) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=t("inline.button_install", lang),
                url=f"tg://kpm_install?plugin={plugin_id}",
                style="primary",
            ),
            InlineKeyboardButton(
                text=t("inline.button_refresh", lang),
                url="tg://kpm_list",
            ),
        ]
    ]

    pick = _callback(PICK_PREFIX, plugin_id)
    if pick:
        rows.append([InlineKeyboardButton(text=t("inline.button_send_file", lang), callback_data=pick)])

    rows.append([InlineKeyboardButton(text=t("inline.button_about", lang), url=KPM_FORUM_URL)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _version_keyboard(plugin_id: str, entry: Dict, lang: str) -> InlineKeyboardMarkup:
    rows = []

    current = _callback(GET_PREFIX, plugin_id)
    if current:
        rows.append([
            InlineKeyboardButton(
                text=t("inline.button_version", lang, version=str(entry.get("version") or "N/A")),
                callback_data=current,
            )
        ])

    legacy = entry.get("legacy_version") or {}
    for version in reversed(list(legacy.keys())[-MAX_VERSION_BUTTONS:]):
        data = _callback(GET_PREFIX, plugin_id, version)
        if data:
            rows.append([
                InlineKeyboardButton(
                    text=t("inline.button_version", lang, version=version),
                    callback_data=data,
                )
            ])

    back = _callback(BACK_PREFIX, plugin_id)
    if back:
        rows.append([InlineKeyboardButton(text=t("inline.button_back", lang), callback_data=back)])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_inline_result(plugin_id: str, entry: Dict, lang: str) -> InlineQueryResultArticle:
    version = str(entry.get("version") or "N/A")
    author = str(entry.get("author") or "N/A")
    description = get_localized_description(entry, lang)
    summary = " · ".join(
        part for part in (f"v{version}", author, description.replace("\\n", " ")[:100]) if part
    )

    return InlineQueryResultArticle(
        id=plugin_id[:64],
        title=str(entry.get("name") or plugin_id)[:128],
        description=summary[:256],
        input_message_content=InputTextMessageContent(
            message_text=_card_text(plugin_id, entry, lang),
            parse_mode="HTML",
        ),
        reply_markup=_keyboard(plugin_id, lang),
    )


def _resolve_file(entry: Dict, version: str) -> Optional[Tuple[str, str]]:
    if version:
        source = (entry.get("legacy_version") or {}).get(version) or {}
        url = str(source.get("url") or "")
    else:
        url = str(entry.get("url") or "")
    if not url.startswith(("http://", "https://")):
        return None
    return url, os.path.basename(url)


async def _fetch_file(url: str) -> bytes:
    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as resp:
            resp.raise_for_status()
            data = await resp.read()
    if len(data) > TELEGRAM_UPLOAD_LIMIT:
        raise ValueError("файл больше лимита Telegram")
    return data


@router.inline_query()
async def handle_inline_query(query: InlineQuery, lang: str):
    offset = int(query.offset) if query.offset.isdigit() else 0
    matches = search_store(query.query, lang)
    page = matches[offset:offset + PAGE_SIZE]

    results = [build_inline_result(plugin_id, entry, lang) for plugin_id, entry in page]
    next_offset = str(offset + PAGE_SIZE) if offset + PAGE_SIZE < len(matches) else ""

    await query.answer(
        results=results,
        cache_time=60,
        is_personal=False,
        next_offset=next_offset,
    )


@router.callback_query(F.data.startswith(PICK_PREFIX))
async def handle_inline_pick(call: CallbackQuery, bot: Bot, lang: str):
    if not call.inline_message_id:
        await call.answer(t("inline.only_inline", lang), show_alert=True)
        return

    plugin_id, _, _ = call.data[len(PICK_PREFIX):].partition(":")
    entry = get_plugin_entry(plugin_id)
    if not entry:
        print(f"⚠️ Инлайн: плагин '{plugin_id}' не найден в {STORE_JSON_FILE}")
        await call.answer(t("inline.file_not_found", lang), show_alert=True)
        return

    await bot.edit_message_reply_markup(
        inline_message_id=call.inline_message_id,
        reply_markup=_version_keyboard(plugin_id, entry, lang),
    )
    await call.answer()


@router.callback_query(F.data.startswith(BACK_PREFIX))
async def handle_inline_back(call: CallbackQuery, bot: Bot, lang: str):
    if not call.inline_message_id:
        await call.answer(t("inline.only_inline", lang), show_alert=True)
        return

    plugin_id, _, _ = call.data[len(BACK_PREFIX):].partition(":")
    await bot.edit_message_reply_markup(
        inline_message_id=call.inline_message_id,
        reply_markup=_keyboard(plugin_id, lang),
    )
    await call.answer()


@router.callback_query(F.data.startswith(GET_PREFIX))
async def handle_inline_download(call: CallbackQuery, bot: Bot, lang: str):
    if not call.inline_message_id:
        await call.answer(t("inline.only_inline", lang), show_alert=True)
        return

    plugin_id, _, version = call.data[len(GET_PREFIX):].partition(":")
    entry = get_plugin_entry(plugin_id)
    if not entry:
        print(f"⚠️ Инлайн: плагин '{plugin_id}' не найден в {STORE_JSON_FILE}")
    source = _resolve_file(entry, version) if entry else None
    if entry and not source:
        print(f"⚠️ Инлайн: у '{plugin_id}' нет http-ссылки для версии '{version or 'текущая'}'")
    if not source:
        await call.answer(t("inline.file_not_found", lang), show_alert=True)
        return

    url, filename = source
    user_chat = call.from_user.id
    error = None
    try:
        data = await _fetch_file(url)
        staged = await bot.send_document(
            user_chat,
            BufferedInputFile(data, filename=filename),
            disable_notification=True,
        )
        file_id = staged.document.file_id
        try:
            await bot.delete_message(user_chat, staged.message_id)
        except Exception:
            pass

        await bot.edit_message_media(
            inline_message_id=call.inline_message_id,
            media=InputMediaDocument(
                media=file_id,
                caption=_card_text(plugin_id, entry, lang, CAPTION_DESCRIPTION_LIMIT),
                parse_mode="HTML",
            ),
            reply_markup=_keyboard(plugin_id, lang),
        )
    except (TelegramBadRequest, TelegramForbiddenError) as ex:
        print(f"⚠️ Telegram не принял файл из инлайна: {ex}")
        error = t("inline.start_bot_first", lang)
    except Exception as ex:
        print(f"⚠️ Не удалось отправить файл из инлайн-карточки: {ex}")
        error = t("inline.download_error", lang)

    if error:
        await call.answer(error, show_alert=True)
    else:
        await call.answer()
