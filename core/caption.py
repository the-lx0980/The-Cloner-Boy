# core/caption.py

import re
from typing import Dict, Any, Optional, List
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton


def process_caption(message: Message, settings: Dict[str, Any]) -> Optional[str]:
    """
    Process caption according to target settings.
    Returns final caption string or None.
    """
    original = message.caption or message.text or ""

    # 1. Start with original
    caption = original

    # 2. Text Replacements
    if settings.get("replace_enabled", False):
        replacements: List[Dict[str, str]] = settings.get("replacements", [])
        for rule in replacements:
            old = rule.get("from", "")
            new = rule.get("to", "")
            if old:
                caption = caption.replace(old, new)

    # 3. Remove Links
    if settings.get("remove_links", False):
        # Remove http/https/t.me/telegram.me links
        caption = re.sub(
            r"https?://\S+|www\.\S+|t\.me/\S+|telegram\.me/\S+|telegram\.dog/\S+",
            "",
            caption,
            flags=re.IGNORECASE
        )
        # Clean extra spaces/newlines
        caption = re.sub(r"\n{3,}", "\n\n", caption)
        caption = re.sub(r"[ \t]{2,}", " ", caption)
        caption = caption.strip()

    # 4. Caption Template
    if settings.get("caption_enabled", False):
        template = settings.get("caption_template", "{caption}")
        caption = template.replace("{caption}", caption)

    # If final caption is empty → return None (so no caption is sent)
    if not caption or not caption.strip():
        return None

    return caption


def build_inline_keyboard(settings: Dict[str, Any]) -> Optional[InlineKeyboardMarkup]:
    """
    Build InlineKeyboardMarkup from settings.
    """
    buttons_data = settings.get("inline_buttons", [])
    if not buttons_data:
        return None

    keyboard = []
    for row in buttons_data:
        btn_row = []
        for btn in row:
            text = btn.get("text")
            url = btn.get("url")
            if text and url:
                btn_row.append(InlineKeyboardButton(text=text, url=url))
        if btn_row:
            keyboard.append(btn_row)

    if not keyboard:
        return None

    return InlineKeyboardMarkup(keyboard)