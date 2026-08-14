# core/forwarder.py
# Final Phase-1 Engine with Account Rotation + Better Error Handling

import asyncio
import logging
from typing import Dict, Any, Optional, AsyncGenerator, Union, List, Callable, Awaitable, Tuple

from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import (
    FloodWait, SlowmodeWait, 
    UserDeactivated, AuthKeyUnregistered, SessionRevoked
)
from pyrogram.enums import ParseMode

from database import (
    update_job_stats, set_job_status,
    increment_account_forwarded, increment_stats,
    JobStatus, AccountStatus
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
    job_id: Optional[str] = None,
    account_id: Optional[str] = None,
    account_ids: Optional[List[str]] = None,
    strategy: str = "sequential",
    # Callback for account rotation (provided by worker)
    get_new_client_callback: Optional[
        Callable[[int, List[str], str], Awaitable[Tuple[Optional[Client], Optional[str]]]]
    ] = None,
):
    settings = target.get("settings", {})
    target_chat_id = target["chat_id"]
    delay = float(settings.get("delay", 1.0))
    forward_tag = settings.get("forward_tag", False)
    anti_dup = settings.get("anti_duplicate", True)

    stats = ForwardStats()
    CANCEL = cancel_flag or {}

    current_client = client
    current_account_id = account_id

    try:
        async for message in custom_iter_messages(
            current_client, source_chat_id, limit=last_msg_id, offset=skip
        ):
            # ----- Cancel / Job status check -----
            if CANCEL.get(user_id):
                if job_id:
                    set_job_status(user_id, job_id, JobStatus.CANCELLED.value)
                return stats

            if job_id:
                from database import get_job
                fresh = get_job(user_id, job_id)
                if not fresh or fresh.get("status") != JobStatus.RUNNING.value:
                    logger.info(f"Job {job_id} stopped by user")
                    return stats

            stats.fetched += 1

            # ----- Filters -----
            should, reason = should_process_message(message, settings)
            if not should:
                if reason == "deleted":
                    stats.skipped_deleted += 1
                else:
                    stats.skipped_filter += 1
                if job_id:
                    update_job_stats(user_id, job_id, {"fetched": 1}, current_msg_id=message.id)
                continue

            # ----- Anti-Duplicate -----
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

            final_caption = process_caption(message, settings)
            reply_markup = build_inline_keyboard(settings)

            # ==================== SEND ====================
            try:
                if forward_tag:
                    await current_client.forward_messages(
                        chat_id=target_chat_id,
                        from_chat_id=source_chat_id,
                        message_ids=message.id
                    )
                else:
                    if message.media:
                        media = getattr(message, message.media.value, None)
                        if media and hasattr(media, "file_id"):
                            await current_client.send_cached_media(
                                chat_id=target_chat_id,
                                file_id=media.file_id,
                                caption=final_caption,
                                parse_mode=ParseMode.HTML,
                                reply_markup=reply_markup
                            )
                        else:
                            await current_client.copy_message(
                                chat_id=target_chat_id,
                                from_chat_id=source_chat_id,
                                message_id=message.id,
                                caption=final_caption,
                                parse_mode=ParseMode.HTML,
                                reply_markup=reply_markup
                            )
                    else:
                        await current_client.send_message(
                            chat_id=target_chat_id,
                            text=final_caption or message.text or "",
                            parse_mode=ParseMode.HTML,
                            reply_markup=reply_markup,
                            disable_web_page_preview=True
                        )

                stats.forwarded += 1

                # ---------- Account Limit + Rotation ----------
                if current_account_id:
                    updated = increment_account_forwarded(user_id, current_account_id, 1)

                    if updated and updated.get("status") == AccountStatus.SLEEPING.value:
                        logger.info(f"Account {current_account_id} reached limit → rotating...")

                        if get_new_client_callback and account_ids:
                            new_client, new_acc_id = await get_new_client_callback(
                                user_id, account_ids, strategy
                            )
                            if new_client and new_acc_id:
                                current_client = new_client
                                current_account_id = new_acc_id
                                logger.info(f"Switched to account {new_acc_id}")
                            else:
                                logger.warning("No available accounts left → pausing job")
                                if job_id:
                                    set_job_status(
                                        user_id, job_id,
                                        JobStatus.PAUSED.value,
                                        "All accounts sleeping or unavailable"
                                    )
                                return stats

                # Stats update
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
                wait = e.value
                logger.warning(f"FloodWait {wait}s (account {current_account_id})")
                await asyncio.sleep(wait)

            except (UserDeactivated, AuthKeyUnregistered, SessionRevoked) as e:
                logger.error(f"Account {current_account_id} is dead: {e}")
                if get_new_client_callback and account_ids:
                    new_client, new_acc_id = await get_new_client_callback(
                        user_id, account_ids, strategy
                    )
                    if new_client and new_acc_id:
                        current_client = new_client
                        current_account_id = new_acc_id
                        logger.info(f"Recovered → switched to {new_acc_id}")
                        continue

                if job_id:
                    set_job_status(user_id, job_id, JobStatus.PAUSED.value, f"Account error: {e}")
                return stats

            except Exception as e:
                logger.exception(f"Error on message {message.id}: {e}")
                stats.errors += 1
                if job_id:
                    update_job_stats(user_id, job_id, {"errors": 1}, current_msg_id=message.id)
                continue

            if delay > 0:
                await asyncio.sleep(delay)

    except Exception as e:
        logger.exception(f"Forwarder crashed: {e}")
        if job_id:
            set_job_status(user_id, job_id, JobStatus.FAILED.value, str(e))
        raise

    return stats
