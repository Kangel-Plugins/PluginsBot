from telebot import types

USE_CUSTOM_EMOJI: bool = True
_CHECKED_WITH_TELEGRAM: bool = False


def set_custom_emoji_enabled(enabled: bool):
    global USE_CUSTOM_EMOJI, _CHECKED_WITH_TELEGRAM
    USE_CUSTOM_EMOJI = bool(enabled)
    _CHECKED_WITH_TELEGRAM = True


def is_custom_emoji_enabled() -> bool:
    return USE_CUSTOM_EMOJI


def check_and_update_from_message(message: types.Message) -> bool:
    global USE_CUSTOM_EMOJI, _CHECKED_WITH_TELEGRAM
    if not message:
        return USE_CUSTOM_EMOJI

    has_custom = False

    if hasattr(message, "entities") and message.entities:
        for ent in message.entities:
            if getattr(ent, "type", None) == "custom_emoji":
                has_custom = True
                break

    if not has_custom and hasattr(message, "caption_entities") and message.caption_entities:
        for ent in message.caption_entities:
            if getattr(ent, "type", None) == "custom_emoji":
                has_custom = True
                break

    if not has_custom and hasattr(message, "reply_markup") and message.reply_markup:
        kb = getattr(message.reply_markup, "inline_keyboard", [])
        for row in kb:
            for btn in row:
                if getattr(btn, "icon_custom_emoji_id", None):
                    has_custom = True
                    break

    _CHECKED_WITH_TELEGRAM = True
    if USE_CUSTOM_EMOJI != has_custom:
        USE_CUSTOM_EMOJI = has_custom

    return has_custom


ID_CHECK = "5233491489253793257"
ID_CROSS = "5233384381359366546"
ID_WAVE = "5235667732002808587"
ID_CLIPBOARD = "5233744922389029275"
ID_WARNING = "5233714604214886573"
ID_TRASH = "5235438316324691636"
ID_PLUS = "5233355635143255039"
ID_REFRESH = "5235862543129419862"
ID_BACK = "5233605713909033365"
ID_DOWNLOAD = "5235463308739387866"
ID_TOOLS = "5233428323169774559"
ID_PALETTE = "5233314764234466241"
ID_INFO = "5233526471762421430"
ID_GAME = "5235808044289401061"
ID_MESSAGES = "5235885297866152423"
ID_LIBRARY = "5233378780722009784"
ID_CHART = "5235804664150141868"

ID_USER = "5233481756857901308"
ID_PACKAGE = "5233414918576845450"
ID_MEMO = "5235608843706212934"
ID_DEVELOPER = "5233296484853652660"
ID_PIN = "5235520277185603109"
ID_MOBILE = "5235652115501721729"
ID_MOBILE_ARROW = "5233512190996163964"
ID_FOLDER = "5233614948088718311"
ID_FILE = "5233657433905210706"
ID_LINK = "5235930343483155348"
ID_CHART_TEXT = "5233608535702547260"
ID_LIBRARY_TEXT = "5233677315308824241"
ID_MESSAGES_TEXT = "5233744144999949808"


def e(emoji_id: str | None, fallback: str) -> str:
    if USE_CUSTOM_EMOJI and emoji_id:
        return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'
    return fallback


def make_inline_button(
    text: str,
    callback_data: str | None = None,
    url: str | None = None,
    emoji_id: str | None = None,
    fallback_emoji: str = "",
    style: str | None = None,
) -> types.InlineKeyboardButton:
    if USE_CUSTOM_EMOJI and emoji_id:
        kwargs = {}
        if style:
            kwargs["style"] = style
        return types.InlineKeyboardButton(
            text=text,
            callback_data=callback_data,
            url=url,
            icon_custom_emoji_id=emoji_id,
            **kwargs,
        )
    else:
        label = f"{fallback_emoji} {text}".strip() if fallback_emoji else text
        kwargs = {}
        if style:
            kwargs["style"] = style
        return types.InlineKeyboardButton(
            text=label,
            callback_data=callback_data,
            url=url,
            **kwargs,
        )


class _EmojiAccessor:
    @property
    def EMOJI_CHECK(self): return e(ID_CHECK, "✅")
    @property
    def EMOJI_CROSS(self): return e(ID_CROSS, "❌")
    @property
    def EMOJI_WAVE(self): return e(ID_WAVE, "👋")
    @property
    def EMOJI_MEMO(self): return e(ID_MEMO, "📝")
    @property
    def EMOJI_TOOLS(self): return e(ID_TOOLS, "🛠")
    @property
    def EMOJI_PALETTE(self): return e(ID_PALETTE, "🎨")
    @property
    def EMOJI_INFO(self): return e(ID_INFO, "ℹ️")
    @property
    def EMOJI_GAME(self): return e(ID_GAME, "🎮")
    @property
    def EMOJI_MESSAGES(self): return e(ID_MESSAGES, "💬")
    @property
    def EMOJI_MESSAGES_TEXT(self): return e(ID_MESSAGES_TEXT, "💬")
    @property
    def EMOJI_LIBRARY(self): return e(ID_LIBRARY, "📚")
    @property
    def EMOJI_LIBRARY_TEXT(self): return e(ID_LIBRARY_TEXT, "📚")
    @property
    def EMOJI_CLIPBOARD(self): return e(ID_CLIPBOARD, "📋")
    @property
    def EMOJI_PACKAGE(self): return e(ID_PACKAGE, "📦")
    @property
    def EMOJI_DEVELOPER(self): return e(ID_DEVELOPER, "👨‍💻")
    @property
    def EMOJI_PIN(self): return e(ID_PIN, "📌")
    @property
    def EMOJI_MOBILE(self): return e(ID_MOBILE, "📱")
    @property
    def EMOJI_MOBILE_ARROW(self): return e(ID_MOBILE_ARROW, "📲")
    @property
    def EMOJI_FOLDER(self): return e(ID_FOLDER, "📂")
    @property
    def EMOJI_CHART(self): return e(ID_CHART, "📊")
    @property
    def EMOJI_CHART_TEXT(self): return e(ID_CHART_TEXT, "📊")
    @property
    def EMOJI_FILE(self): return e(ID_FILE, "📄")
    @property
    def EMOJI_LINK(self): return e(ID_LINK, "🔗")
    @property
    def EMOJI_USER(self): return e(ID_USER, "👤")
    @property
    def EMOJI_WARNING(self): return e(ID_WARNING, "⚠️")
    @property
    def EMOJI_TRASH(self): return e(ID_TRASH, "🗑")
    @property
    def EMOJI_PLUS(self): return e(ID_PLUS, "➕")
    @property
    def EMOJI_REFRESH(self): return e(ID_REFRESH, "🔄")
    @property
    def EMOJI_BACK(self): return e(ID_BACK, "◀️")
    @property
    def EMOJI_DOWNLOAD(self): return e(ID_DOWNLOAD, "⬇️")


_accessor = _EmojiAccessor()


def __getattr__(name: str):
    if hasattr(_accessor, name):
        return getattr(_accessor, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
