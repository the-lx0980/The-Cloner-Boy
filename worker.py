# worker.py
# Forwarding Worker - Phase 1
# Runs as a separate process from the Management Bot

import asyncio
import logging
import signal
import sys
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from pyrogram import Client
from pyrogram.errors import FloodWait, UserDeactivated, AuthKeyUnregistered, SessionRevoked
from pyrogram.enums import ParseMode

from config import Config
from database import (
    db, get_active_jobs, get_job, update_job, set_job_status,
    update_job_stats, get_target, get_account, get_bot,
    get_available_accounts, get_next_available_account,
    increment_account_forwarded, wake_sleeping_accounts,
    JobStatus, MethodType, AccountStatus
)
from core.forwarder import forward_messages
from core.filters import should_process_message
from core.caption import process_caption, build_inline_keyboard
from core.anti_duplicate import check_and_mark_duplicate

# ==================== LOGGING ====================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [WORKER] - [%(levelname)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("worker")
logging.getLogger("pyrogram").setLevel(logging.WARNING)
logging.getLogger("pymongo").setLevel(logging.WARNING)


# ==================== GLOBAL STATE ====================
RUNNING = True
ACTIVE_CLIENTS: Dict[str, Client] = {}          # account_id / bot_id → Client
CURRENT_JOBS: Dict[str, asyncio.Task] = {}      # job_id → Task


def shutdown(sig, frame):
    global RUNNING
    logger.warning("Shutdown signal received. Stopping worker...")
    RUNNING = False


signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)


# ==================== CLIENT MANAGEMENT ====================

async def get_or_create_bot_client(bot_doc: Dict) -> Optional[Client]:
    bot_id = bot_doc["bot_id"]
    if bot_id in ACTIVE_CLIENTS:
        return ACTIVE_CLIENTS[bot_id]

    try:
        client = Client(
            name=f"bot_{bot_id}",
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            bot_token=bot_doc["bot_token"],
            in_memory=True,
            parse_mode=ParseMode.HTML
        )
        await client.start()
        ACTIVE_CLIENTS[bot_id] = client
        logger.info(f"Bot client started: {bot_doc.get('name')} ({bot_id})")
        return client
    except Exception as e:
        logger.error(f"Failed to start bot {bot_id}: {e}")
        return None


async def get_or_create_user_client(account_doc: Dict) -> Optional[Client]:
    account_id = account_doc["account_id"]
    if account_id in ACTIVE_CLIENTS:
        return ACTIVE_CLIENTS[account_id]

    session_string = account_doc.get("session_string")
    if not session_string:
        logger.error(f"Account {account_id} has no session_string")
        return None

    try:
        client = Client(
            name=f"user_{account_id}",
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            session_string=session_string,
            in_memory=True,
            parse_mode=ParseMode.HTML
        )
        await client.start()
        ACTIVE_CLIENTS[account_id] = client
        logger.info(f"User client started: {account_doc.get('name')} ({account_id})")
        return client
    except (UserDeactivated, AuthKeyUnregistered, SessionRevoked) as e:
        logger.error(f"Account {account_id} session invalid: {e}")
        # Mark account as error
        from database import set_account_status
        set_account_status(account_doc["user_id"], account_id, AccountStatus.ERROR.value, str(e))
        return None
    except Exception as e:
        logger.error(f"Failed to start user client {account_id}: {e}")
        return None


async def close_all_clients():
    for client_id, client in list(ACTIVE_CLIENTS.items()):
        try:
            await client.stop()
            logger.info(f"Client stopped: {client_id}")
        except Exception as e:
            logger.error(f"Error stopping client {client_id}: {e}")
    ACTIVE_CLIENTS.clear()


# ==================== JOB RUNNER ====================

async def run_single_job(job: Dict[str, Any]):
    """
    Execute one job completely (or until paused/cancelled).
    """
    job_id = job["job_id"]
    user_id = job["user_id"]
    method = job.get("method")
    source_chat_id = job["source_chat_id"]
    target_chat_ids = job.get("target_chat_ids", [])
    last_msg_id = job.get("last_msg_id", 0)
    current_msg_id = job.get("current_msg_id", job.get("skip", 0))
    account_ids = job.get("account_ids", [])
    bot_id = job.get("bot_id")

    logger.info(f"Starting job {job_id} | method={method} | from={current_msg_id} → {last_msg_id}")

    try:
        # ========== GET CLIENT ==========
        client = None
        current_account_id = None

        if method == MethodType.BOT.value:
            bot = get_bot(user_id, bot_id)
            if not bot or bot.get("status") != "active":
                set_job_status(user_id, job_id, JobStatus.FAILED.value, "Bot not available")
                return
            client = await get_or_create_bot_client(bot)
            if not client:
                set_job_status(user_id, job_id, JobStatus.FAILED.value, "Failed to start bot client")
                return

        elif method == MethodType.USER.value:
            # Wake any sleeping accounts first
            wake_sleeping_accounts(user_id)

            account = get_next_available_account(user_id, account_ids)
            if not account:
                set_job_status(user_id, job_id, JobStatus.PAUSED.value, "No available accounts")
                logger.warning(f"Job {job_id}: No available accounts, pausing")
                return

            current_account_id = account["account_id"]
            client = await get_or_create_user_client(account)
            if not client:
                set_job_status(user_id, job_id, JobStatus.PAUSED.value, "Account client failed")
                return
        else:
            set_job_status(user_id, job_id, JobStatus.FAILED.value, f"Unknown method: {method}")
            return

        # ========== PROCESS EACH TARGET ==========
        for target_chat_id in target_chat_ids:
            # Re-check job status (in case user paused/cancelled)
            fresh_job = get_job(user_id, job_id)
            if not fresh_job or fresh_job.get("status") != JobStatus.RUNNING.value:
                logger.info(f"Job {job_id} is no longer running. Stopping.")
                return

            target = get_target(user_id, target_chat_id)
            if not target:
                logger.warning(f"Target {target_chat_id} not found, skipping")
                continue

            logger.info(f"Job {job_id} → Target {target.get('title')} ({target_chat_id})")

            # Call the core forwarder
            await forward_messages(
                client=client,
                user_id=user_id,
                source_chat_id=source_chat_id,
                target=target,
                last_msg_id=last_msg_id,
                skip=current_msg_id,
                progress_message=None,          # Worker has no progress message
                cancel_flag=None,
                job_id=job_id,
                account_id=current_account_id,
                account_ids=account_ids,
                strategy=job.get("account_strategy", "sequential")
            )

        # Job completed
        set_job_status(user_id, job_id, JobStatus.COMPLETED.value)
        logger.info(f"Job {job_id} completed successfully")

    except asyncio.CancelledError:
        logger.info(f"Job {job_id} was cancelled")
        set_job_status(user_id, job_id, JobStatus.CANCELLED.value)
    except Exception as e:
        logger.exception(f"Job {job_id} crashed: {e}")
        set_job_status(user_id, job_id, JobStatus.FAILED.value, str(e))


# ==================== MAIN WORKER LOOP ====================

async def worker_loop():
    logger.info("Worker loop started")

    while RUNNING:
        try:
            # 1. Wake sleeping accounts
            woken = wake_sleeping_accounts()
            if woken:
                logger.info(f"Woke up {woken} sleeping accounts")

            # 2. Get all RUNNING jobs
            jobs = get_active_jobs()
            running_jobs = [j for j in jobs if j.get("status") == JobStatus.RUNNING.value]

            for job in running_jobs:
                job_id = job["job_id"]

                # Skip if already being processed
                if job_id in CURRENT_JOBS and not CURRENT_JOBS[job_id].done():
                    continue

                # Start new task for this job
                task = asyncio.create_task(run_single_job(job))
                CURRENT_JOBS[job_id] = task
                logger.info(f"Spawned task for job {job_id}")

            # 3. Cleanup finished tasks
            finished = [jid for jid, task in CURRENT_JOBS.items() if task.done()]
            for jid in finished:
                del CURRENT_JOBS[jid]

            # 4. Sleep before next poll
            await asyncio.sleep(8)          # Poll every 8 seconds

        except Exception as e:
            logger.exception(f"Worker loop error: {e}")
            await asyncio.sleep(15)

    # Shutdown
    logger.info("Worker shutting down...")
    for task in CURRENT_JOBS.values():
        task.cancel()
    await close_all_clients()
    logger.info("Worker stopped cleanly")


# ==================== ENTRY POINT ====================

async def main():
    logger.info("Connecting to MongoDB...")
    try:
        db.connect()
        logger.info("✅ MongoDB connected")
    except Exception as e:
        logger.error(f"❌ MongoDB connection failed: {e}")
        sys.exit(1)

    logger.info("Starting Forwarding Worker...")
    await worker_loop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user")