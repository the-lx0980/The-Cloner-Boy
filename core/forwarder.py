# core/forwarder.py

import asyncio
import logging
from typing import Dict, Any, Optional
from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import FloodWait, RPCError
from pyrogram.enums import ParseMode

from database import get_setting
from core.filters import should_process_message, get_unique_file_id
from core.caption import process_caption, build_inline_keyboard
from core.anti_duplicate import check_and_mark_duplicate

logger = logging.getLogger(__name__)


class ForwardStats:
    def __init__(self):
        self.total = 0
        self.fetched = 0
        self.forwarded = 0
        self.skipped_deleted = 0
        self.skipped_filter = 0
        self.skipped_duplicate = 0
        self.errors = 0


async def forward_messages(
    client: Client,
    user_id: int,
    source_chat_id: int | str,
    target: Dict[str, Any],
    last_msg_id: int,
    skip: int = 0,
    progress_message: Optional[Message] = None,
    cancel_flag: Optional[Dict] = None
):
    """
    Main forwarding engine.

    Parameters:
        client            : Pyrogram/Kurigram client
        user_id           : Who started the process
        source_chat_id    : Source channel/group
        target            : Full target document from MongoDB
        last_msg_id       : Last message ID (start from here going backwards)
        skip              : How many messages to skip from the end
        progress_message  : Message to edit for progress
        cancel_flag       : Dict like {user_id: False}  → set True to cancel
    """

    settings = target.get("settings", {})
    target_chat_id = target["chat_id"]
    delay = float(settings.get("delay", 1.0))
    forward_tag = settings.get("forward_tag", False)
    anti_dup = settings.get("anti_duplicate", True)

    stats = ForwardStats()
    stats.total = last_msg_id

    current = skip
    CANCEL = cancel_flag if cancel_flag is not None else {}

    try:
        async for message in client.iter_messages(
            source_chat_id,
            offset_id=last_msg_id + 1,   # start from latest
            reverse=True                 # go from old → new? Adjust as needed
        ):
            # Safety: stop when we reach skip point
            if message.id <= skip:
                break

            if CANCEL.get(user_id):
                if progress_message:
                    await progress_message.edit_text(
                        f"**🛑 Forwarding Cancelled**\n\n"
                        f"Completed: `{current}` / `{stats.total}`\n"
                        f"Forwarded: `{stats.forwarded}`"
                    )
                return stats

            current = message.id
            stats.fetched += 1

            # -------- Progress Update (every 20 messages) --------
            if progress_message and stats.fetched % 20 == 0:
                try:
                    await progress_message.edit_text(
                        f"**🚀 Forwarding in progress...**\n\n"
                        f"Source → Target\n"
                        f"`{source_chat_id}` → `{target_chat_id}`\n\n"
                        f"**Progress:** `{stats.fetched}` fetched\n"
                        f"**Forwarded:** `{stats.forwarded}`\n"
                        f"**Skipped (filter):** `{stats.skipped_filter}`\n"
                        f"**Skipped (duplicate):** `{stats.skipped_duplicate}`\n"
                        f"**Deleted:** `{stats.skipped_deleted}`\n\n"
                        f"Send `cancel` to stop."
                    )
                except Exception:
                    pass

            # -------- Filters --------
            should, reason = should_process_message(message, settings)
            if not should:
                if reason == "deleted":
                    stats.skipped_deleted += 1
                else:
                    stats.skipped_filter += 1
                continue

            # -------- Anti-Duplicate --------
            is_dup = check_and_mark_duplicate(
                user_id=user_id,
                target_chat_id=target_chat_id,
                message=message,
                anti_duplicate_enabled=anti_dup
            )
            if is_dup:
                stats.skipped_duplicate += 1
                continue

            # -------- Process Caption --------
            final_caption = process_caption(message, settings)
            reply_markup = build_inline_keyboard(settings)

            # -------- Send --------
            try:
                if forward_tag:
                    # Keep original forward tag
                    await client.forward_messages(
                        chat_id=target_chat_id,
                        from_chat_id=source_chat_id,
                        message_ids=message.id
                    )
                else:
                    # Clean copy / send
                    if message.media:
                        media = getattr(message, message.media.value, None)
                        if media and hasattr(media, "file_id"):
                            await client.send_cached_media(
                                chat_id=target_chat_id,
                                file_id=media.file_id,
                                caption=final_caption,
                                parse_mode=ParseMode.HTML,
                                reply_markup=reply_markup
                            )
                        else:
                            # Fallback
                            await client.copy_message(
                                chat_id=target_chat_id,
                                from_chat_id=source_chat_id,
                                message_id=message.id,
                                caption=final_caption,
                                parse_mode=ParseMode.HTML,
                                reply_markup=reply_markup
                            )
                    else:
                        # Pure text
                        await client.send_message(
                            chat_id=target_chat_id,
                            text=final_caption or message.text,
                            parse_mode=ParseMode.HTML,
                            reply_markup=reply_markup,
                            disable_web_page_preview=True
                        )

                stats.forwarded += 1

            except FloodWait as e:
                logger.warning(f"FloodWait: sleeping {e.value}s")
                await asyncio.sleep(e.value)
                # Retry once
                try:
                    if message.media:
                        media = getattr(message, message.media.value, None)
                        if media and hasattr(media, "file_id"):
                            await client.send_cached_media(
                                chat_id=target_chat_id,
                                file_id=media.file_id,
                                caption=final_caption,
                                parse_mode=ParseMode.HTML,
                                reply_markup=reply_markup
                            )
                    else:
                        await client.send_message(
                            chat_id=target_chat_id,
                            text=final_caption or message.text,
                            parse_mode=ParseMode.HTML,
                            reply_markup=reply_markup
                        )
                    stats.forwarded += 1
                except Exception as retry_err:
                    logger.error(f"Retry failed: {retry_err}")
                    stats.errors += 1

            except Exception as e:
                logger.exception(f"Error forwarding message {message.id}: {e}")
                stats.errors += 1
                continue

            # -------- Delay --------
            if delay > 0:
                await asyncio.sleep(delay)

    except Exception as e:
        logger.exception(f"Forwarding engine crashed: {e}")
        if progress_message:
            await progress_message.edit_text(
                f"**❌ Forwarding Error**\n\n`{e}`\n\n"
                f"Forwarded so far: `{stats.forwarded}`"
            )
        raise

    # -------- Final Report --------
    if progress_message:
        await progress_message.edit_text(
            f"**✅ Forwarding Completed!**\n\n"
            f"**Source:** `{source_chat_id}`\n"
            f"**Target:** `{target_chat_id}`\n\n"
            f"**Fetched:** `{stats.fetched}`\n"
            f"**Successfully Forwarded:** `{stats.forwarded}`\n"
            f"**Skipped (Filter):** `{stats.skipped_filter}`\n"
            f"**Skipped (Duplicate):** `{stats.skipped_duplicate}`\n"
            f"**Deleted Messages:** `{stats.skipped_deleted}`\n"
            f"**Errors:** `{stats.errors}`"
        )

    return stats