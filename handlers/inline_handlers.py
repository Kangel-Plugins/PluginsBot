import html
from typing import Dict

from aiogram import Router
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
)

from PluginsBot.utils.i18n import t
from PluginsBot.utils.store_utils import get_localized_description, search_store

router = Router()

PAGE_SIZE = 20
DESCRIPTION_LIMIT = 1000


def _build_result(plugin_id: str, entry: Dict, lang: str) -> InlineQueryResultArticle:
    name = str(entry.get("name") or plugin_id)
    version = str(entry.get("version") or "N/A")
    author = str(entry.get("author") or "N/A")
    is_library = entry.get("status") == "library"
    type_label = t("inline.type_library" if is_library else "inline.type_plugin", lang)
    description = get_localized_description(entry, lang)

    text_lines = [
        f"<b>{html.escape(name)}</b>",
        f"{t('label.id', lang)} <code>{html.escape(plugin_id)}</code>",
        f"{t('label.author', lang)} {html.escape(author)}",
        f"{t('label.version', lang)} {html.escape(version)}",
        f"{t('label.type', lang)} {type_label}",
    ]
    min_version = entry.get("min_version")
    if min_version:
        text_lines.append(f"{t('label.min_version', lang)} {html.escape(str(min_version))}")

    if description:
        desc_clean = description.replace("\\n", "\n")
        if len(desc_clean) > DESCRIPTION_LIMIT:
            desc_clean = desc_clean[:DESCRIPTION_LIMIT - 3] + "..."
        text_lines.append(f"\n<blockquote expandable>{html.escape(desc_clean)}</blockquote>")

    buttons = [
        InlineKeyboardButton(
            text=t("inline.button_install", lang),
            url=f"tg://kpm_install?plugin={plugin_id}",
        )
    ]
    file_url = str(entry.get("url") or "")
    if file_url.startswith(("http://", "https://")):
        buttons.append(InlineKeyboardButton(text=t("inline.button_file", lang), url=file_url))

    summary = " · ".join(
        part for part in (f"v{version}", author, description.replace("\\n", " ")[:100]) if part
    )

    return InlineQueryResultArticle(
        id=plugin_id[:64],
        title=name[:128],
        description=summary[:256],
        input_message_content=InputTextMessageContent(
            message_text="\n".join(text_lines),
            parse_mode="HTML",
        ),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[buttons]),
    )


@router.inline_query()
async def handle_inline_query(query: InlineQuery, lang: str):
    offset = int(query.offset) if query.offset.isdigit() else 0
    matches = search_store(query.query, lang)
    page = matches[offset:offset + PAGE_SIZE]

    results = [_build_result(plugin_id, entry, lang) for plugin_id, entry in page]
    next_offset = str(offset + PAGE_SIZE) if offset + PAGE_SIZE < len(matches) else ""

    await query.answer(
        results=results,
        cache_time=60,
        is_personal=False,
        next_offset=next_offset,
    )
