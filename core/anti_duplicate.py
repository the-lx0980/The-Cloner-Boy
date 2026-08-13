# core/anti_duplicate.py

from typing import Optional
from pyrogram.types import Message
from database import is_duplicate, mark_as_forwarded
from core.filters import get_unique_file_id


def check_and_mark_duplicate(
    user_id: int,
    target_chat_id: int,
    message: Message,
    anti_duplicate_enabled: bool
) -> bool:
    """
    Returns True  → This message is DUPLICATE (should skip)
    Returns False → Not duplicate (safe to forward)
    """
    if not anti_duplicate_enabled:
        return False

    unique_id = get_unique_file_id(message)
    if not unique_id:
        # No media → cannot check duplicate
        return False

    if is_duplicate(user_id, target_chat_id, unique_id):
        return True  # Duplicate → skip

    # Mark it now (before sending) to avoid race conditions
    mark_as_forwarded(user_id, target_chat_id, unique_id)
    return False