# core/forwarder.py
# Improved Forwarding Engine - Phase 1
# Compatible with worker.py + database.py

import asyncio
import logging
from typing import Dict, Any, Optional, AsyncGenerator, Union, List

from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import FloodWait, SlowmodeWait
from pyrogram.enums import ParseMode

from database import (
    get_setting,
    update_job_stats,
    set_job_status,
    increment_account_forwarded,
    increment_stats,
    get_next_available_account,
    JobStatus,
)
from core.filters import should_process_message
from core.caption import process_caption, build_inline_keyboard
from core.anti_duplicate import check_and_mark_duplicate

logger = logging.getLogger(__name__)


class ForwardStats:
    def __init__(self):
        self.fetched = 0
        self.forwarded = 0
        self.skipped_deleted = 0
        self.skipped_filter = 0
        self.skipped_duplicate = 0
        self.errors = 0


async def custom_iter_messages(
    client: Client,
    chat_id: Union[int, str],
    limit: int,
    offset: int = 0
) -> AsyncGenerator[Message, None]:
    """
    Efficient message iterator using message IDs.
    limit  = last message ID
    offset = start from this ID (skip)
    """
    current = offset
    while True:
        batch_size = min(200, limit - current)
        if batch_size <= 0:
            return

        message_ids = list(range(current + 1, current + batch_size + 1))
        try:
            messages = await client.get_messages(chat_id, message_ids)
        except Exception as e:
            logger.error(f"Error fetching messages: {e}")
            return

        if not isinstance(messages, list):
            messages = [messages]

        for msg in messages:
            if msg is None or getattr(msg, "empty", False):
                current += 1
                continue
            yield msg
            current += 1


async def forward_messages(
    client: Client,
    user_id: int,
    source_chat_id: Union[int, str],
    target: Dict[str, Any],
    last_msg_id: int,
    skip: int = 0,
    progress_message: Optional[Message] = None,
    cancel_flag: Optional[Dict] = None,
    # ===== Worker parameters =====
    job_id: Optional[str] = None,
    account_id: Optional[str] = None,
    account_ids: Optional[List[str]] = None,
    strategy: str = "sequential",
):
    """
    Main forwarding engine.
    Supports:
    - Job tracking
    - Account limit / sleep
    - Anti-duplicate
    - All target settings
    - Resume from skip/current_msg_id
    """
    settings = target.get("settings", {})
    target_chat_id = target["chat_id"]
    delay = float(settings.get("delay", 1.0))
    forward_tag = settings.get("forward_tag", False)
    anti_dup = settings.get("anti_duplicate", True)

    stats = ForwardStats()
    CANCEL = cancel_flag if cancel_flag is not None else {}

    current_account_id = account_id

    try:
        async for message in custom_iter_messages(
            client,
            source_chat_id,
            limit=last_msg_id,
            offset=skip
        ):
            # ---------- Cancellation check ----------
            if CANCEL.get(user_id):
                if progress_message:
                    try:
                        await progress_message.edit_text(
                            f"**🛑 Forwarding Cancelled**\n\n"
                            f"Fetched: `{stats.fetched}`\n"
                            f"Forwarded: `{stats.forwarded}`"
                        )
                    except Exception:
                        pass
                if job_id:
                    set_job_status(user_id, job_id, JobStatus.CANCELLED.value)
                return stats

            # ---------- Job status check (important for worker) ----------
            if job_id:
                from database import get_job
                fresh_job = get_job(user_id, job_id)
                if not fresh_job or fresh_job.get("status") != JobStatus.RUNNING.value:
                    logger.info(f"Job {job_id} is no longer RUNNING. Stopping forwarder.")
                    return stats

            stats.fetched += 1

            # ---------- Progress update ----------
            if progress_message and stats.fetched % 25 == 0:
                try:
                    await progress_message.edit_text(
                        f"**🚀 Forwarding in progress...**\n\n"
                        f"`{source_chat_id}` → `{target_chat_id}`\n\n"
                        f"**Fetched:** `{stats.fetched}`\n"
                        f"**Forwarded:** `{stats.forwarded}`\n"
                        f"**Skipped (filter):** `{stats.skipped_filter}`\n"
                        f"**Skipped (duplicate):** `{stats.skipped_duplicate}`\n"
                        f"**Deleted:** `{stats.skipped_deleted}`\n\n"
                        f"Send `cancel` to stop."
                    )
                except Exception:
                    pass

            # ---------- FILTERS ----------
            should, reason = should_process_message(message, settings)
            if not should:
                if reason == "deleted":
                    stats.skipped_deleted += 1
                else:
                    stats.skipped_filter += 1

                if job_id:
                    update_job_stats(user_id, job_id, {"fetched": 1}, current_msg_id=message.id)
                continue

            # ---------- ANTI-DUPLICATE ----------
            is_dup = check_and_mark_duplicate(
                user_id=user_id,
                target_chat_id=target_chat_id,
                message=message,
                anti_duplicate_enabled=anti_dup
            )
            if is_dup:
                stats.skipped_duplicate += 1
                if job_id:
                    update_job_stats(
                        user_id, job_id,
                        {"fetched": 1, "skipped_duplicate": 1},
                        current_msg_id=message.id
                    )
                continue

            # ---------- CAPTION + BUTTONS ----------
            final_caption = process_caption(message, settings)
            reply_markup = build_inline_keyboard(settings)

            # ---------- SEND ----------
            try:
                if forward_tag:
                    await client.forward_messages(
                        chat_id=target_chat_id,
                        from_chat_id=source_chat_id,
                        message_ids=message.id
                    )
                else:
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
                            await client.copy_message(
                                chat_id=target_chat_id,
                                from_chat_id=source_chat_id,
                                message_id=message.id,
                                caption=final_caption,
                                parse_mode=ParseMode.HTML,
                                reply_markup=reply_markup
                            )
                    else:
                        await client.send_message(
                            chat_id=target_chat_id,
                            text=final_caption or message.text or "",
                            parse_mode=ParseMode.HTML,
                            reply_markup=reply_markup,
                            disable_web_page_preview=True
                        )

                stats.forwarded += 1

                # ---------- Account limit tracking ----------
                if current_account_id:
                    updated_acc = increment_account_forwarded(user_id, current_account_id, 1)

                    # If account went to sleep → try to switch (Phase 2 will improve this)
                    if updated_acc and updated_acc.get("status") == "sleeping":
                        logger.info(f"Account {current_account_id} reached limit and went to sleep")

                # ---------- Job + Stats update ----------
                if job_id:
                    update_job_stats(
                        user_id, job_id,
                        {"fetched": 1, "forwarded": 1},
                        current_msg_id=message.id
                    )

                increment_stats(user_id, "target", str(target_chat_id), {"forwarded": 1})
                if current_account_id:
                    increment_stats(user_id, "account", current_account_id, {"forwarded": 1})

            except (FloodWait, SlowmodeWait) as e:
                wait_time = e.value
                logger.warning(f"FloodWait/Slowmode: sleeping {wait_time}s")
                await asyncio.sleep(wait_time)

                # Simple one-time retry
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
                            stats.forwarded += 1
                except Exception as retry_err:
                    logger.error(f"Retry after FloodWait failed: {retry_err}")
                    stats.errors += 1

            except Exception as e:
                logger.exception(f"Error forwarding message {message.id}: {e}")
                stats.errors += 1
                if job_id:
                    update_job_stats(user_id, job_id, {"errors": 1}, current_msg_id=message.id)
                continue

            # ---------- Delay between messages ----------
            if delay > 0:
                await asyncio.sleep(delay)

    except Exception as e:
        logger.exception(f"Forwarding engine crashed: {e}")
        if progress_message:
            try:
                await progress_message.edit_text(
                    f"**❌ Forwarding Error**\n\n`{e}`\n\n"
                    f"Forwarded so far: `{stats.forwarded}`"
                )
            except Exception:
                pass
        if job_id:
            set_job_status(user_id, job_id, JobStatus.FAILED.value, str(e))
        raise

    # ---------- Final report ----------
    if progress_message:
        try:
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
        except Exception:
            pass

    if job_id:
        # Note: Worker will mark as COMPLETED after all targets
        pass

    return stats