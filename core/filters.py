# core/filters.py

import re
from typing import Dict, Any, Optional
from pyrogram.types import Message
from pyrogram.enums import MessageMediaType


def should_process_message(message: Message, settings: Dict[str, Any]) -> tuple[bool, str]:
    """
    Check if a message should be forwarded based on all filters.
    Returns (should_process: bool, reason: str)
    """

    # 1. Empty / deleted message
    if message.empty:
        return False, "deleted"

    # 2. Media Type Filter
    allowed_media = settings.get("media_types", [])
    if message.media:
        media_type = message.media.value  # e.g. "photo", "video", "document"
        if media_type not in allowed_media:
            return False, f"media_type:{media_type}"
    else:
        # Pure text message
        if "text" not in allowed_media and not any(
            t in allowed_media for t in ["photo", "video", "document", "audio", "sticker"]
        ):
            # If user only selected media types and this is pure text → skip
            # (optional strictness)
            pass

    # 3. Get text content for word filters
    text_content = ""
    if message.caption:
        text_content = message.caption
    elif message.text:
        text_content = message.text

    text_lower = text_content.lower() if text_content else ""

    # 4. Block Words
    block_words = settings.get("block_words", [])
    if block_words and text_lower:
        for word in block_words:
            if word.lower() in text_lower:
                return False, f"blocked_word:{word}"

    # 5. Whitelist Mode
    if settings.get("whitelist_mode", False):
        whitelist = settings.get("whitelist", [])
        if not whitelist:
            # Whitelist mode ON but empty list → block everything
            return False, "whitelist_empty"

        if text_lower:
            matched = any(w.lower() in text_lower for w in whitelist)
            if not matched:
                return False, "whitelist_miss"
        else:
            # No text + whitelist mode → usually skip
            return False, "whitelist_no_text"

    return True, "ok"


def get_unique_file_id(message: Message) -> Optional[str]:
    """
    Extract unique_file_id from media message.
    Used for anti-duplicate.
    """
    if not message.media:
        return None

    media = getattr(message, message.media.value, None)
    if media and hasattr(media, "file_unique_id"):
        return media.file_unique_id
    return None