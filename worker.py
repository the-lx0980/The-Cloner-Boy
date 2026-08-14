# worker.py
# Forwarding Worker - Phase 1
# Compatible with your current database.py + core/forwarder.py

import asyncio
import logging
import signal
import sys
from typing import Dict, Optional, Any, List

from pyrogram import Client
from pyrogram.errors import (
    FloodWait, UserDeactivated, AuthKeyUnregistered, 
    SessionRevoked, SessionPasswordNeeded
)
from pyrogram.enums import ParseMode

from config import Config
from database import (
    db,
    get_active_jobs,
    get_job,
    set_job_status,
    update_job_stats,
    get_target,
    get_bot,
    get_account,
    get_next_available_account,
    wake_sleeping_accounts,
    JobStatus,
    MethodType,
    AccountStatus,
)
from core.forwarder import forward_messages

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
ACTIVE_CLIENTS: Dict[str, Client] = {}      # key = bot_id or account_id
CURRENT_TASKS: Dict[str, asyncio.Task] = {} # job_id → Task


def handle_shutdown(sig, frame):
    global RUNNING
    logger.warning("Shutdown signal received...")
    RUNNING = False


signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)


# ==================== CLIENT HELPERS ====================

async def get_bot_client(bot_doc: dict) -> Optional[Client]:
    bot_id = bot_doc["bot_id"]
    if bot_id in ACTIVE_CLIENTS:
        return ACTIVE_CLIENTS[bot_id]

    try:
        client = Client(
            name=f"fwd_bot_{bot_id}",
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            bot_token=bot_doc["bot_token"],
            in_memory=True,
            parse_mode=ParseMode.HTML
        )
        await client.start()
        ACTIVE_CLIENTS[bot_id] = client
        logger.info(f"✅ Bot client started → {bot_doc.get('name')} ({bot_id})")
        return client
    except Exception as e:
        logger.error(f"❌ Failed to start bot {bot_id}: {e}")
        return None


async def get_user_client(account_doc: dict) -> Optional[Client]:
    account_id = account_doc["account_id"]
    if account_id in ACTIVE_CLIENTS:
        return ACTIVE_CLIENTS[account_id]

    session_string = account_doc.get("session_string")
    if not session_string:
        logger.error(f"Account {account_id} has no session_string")
        return None

    try:
        client = Client(
            name=f"fwd_user_{account_id}",
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            session_string=session_string,
            in_memory=True,
            parse_mode=ParseMode.HTML
        )
        await client.start()
        ACTIVE_CLIENTS[account_id] = client
        logger.info(f"✅ User client started → {account_doc.get('name')} ({account_id})")
        return client
    except (UserDeactivated, AuthKeyUnregistered, SessionRevoked) as e:
        logger.error(f"❌ Account {account_id} session invalid: {e}")
        from database import set_account_status
        set_account_status(
            account_doc["user_id"],
            account_id,
            AccountStatus.ERROR.value,
            str(e)
        )
        return None
    except Exception as e:
        logger.error(f"❌ Failed to start user client {account_id}: {e}")
        return None


async def close_all_clients():
    for key, client in list(ACTIVE_CLIENTS.items()):
        try:
            await client.stop()
            logger.info(f"Client stopped: {key}")
        except Exception as e:
            logger.error(f"Error stopping {key}: {e}")
    ACTIVE_CLIENTS.clear()


# ==================== SINGLE JOB RUNNER ====================

async def run_job(job: dict):
    job_id = job["job_id"]
    user_id = job["user_id"]
    method = job.get("method")
    source_chat_id = job["source_chat_id"]
    target_chat_ids = job.get("target_chat_ids", [])
    last_msg_id = job.get("last_msg_id", 0)
    current_msg_id = job.get("current_msg_id", job.get("skip", 0))
    account_ids = job.get("account_ids", [])
    bot_id = job.get("bot_id")
    strategy = job.get("account_strategy", "sequential")

    logger.info(
        f"🚀 Job {job_id} started | method={method} | "
        f"from msg {current_msg_id} → {last_msg_id}"
    )

    try:
        # ---------- Get Client ----------
        client = None
        current_account_id = None

        if method == MethodType.BOT.value:
            bot = get_bot(user_id, bot_id)
            if not bot or bot.get("status") != "active":
                set_job_status(user_id, job_id, JobStatus.FAILED.value, "Bot not available or disabled")
                return

            client = await get_bot_client(bot)
            if not client:
                set_job_status(user_id, job_id, JobStatus.FAILED.value, "Could not start bot client")
                return

        elif method == MethodType.USER.value:
            # Wake sleeping accounts
            wake_sleeping_accounts(user_id)

            account = get_next_available_account(user_id, account_ids, strategy)
            if not account:
                set_job_status(user_id, job_id, JobStatus.PAUSED.value, "No available accounts")
                logger.warning(f"Job {job_id}: No available accounts → Paused")
                return

            current_account_id = account["account_id"]
            client = await get_user_client(account)
            if not client:
                set_job_status(user_id, job_id, JobStatus.PAUSED.value, "Account client failed")
                return
        else:
            set_job_status(user_id, job_id, JobStatus.FAILED.value, f"Unknown method: {method}")
            return

        # ---------- Process each Target ----------
        for target_chat_id in target_chat_ids:
            # Check if job was paused/cancelled meanwhile
            fresh = get_job(user_id, job_id)
            if not fresh or fresh.get("status") != JobStatus.RUNNING.value:
                logger.info(f"Job {job_id} is no longer RUNNING. Stopping.")
                return

            target = get_target(user_id, target_chat_id)
            if not target:
                logger.warning(f"Target {target_chat_id} not found, skipping")
                continue

            logger.info(f"Job {job_id} → Target: {target.get('title')} ({target_chat_id})")

            # Call the core engine
            await forward_messages(
                client=client,
                user_id=user_id,
                source_chat_id=source_chat_id,
                target=target,
                last_msg_id=last_msg_id,
                skip=current_msg_id,
                progress_message=None,
                cancel_flag=None,
                job_id=job_id,
                account_id=current_account_id,
                account_ids=account_ids,
                strategy=strategy
            )

        # All targets done
        set_job_status(user_id, job_id, JobStatus.COMPLETED.value)
        logger.info(f"✅ Job {job_id} completed")

    except asyncio.CancelledError:
        logger.info(f"Job {job_id} cancelled")
        set_job_status(user_id, job_id, JobStatus.CANCELLED.value)
    except Exception as e:
        logger.exception(f"Job {job_id} crashed: {e}")
        set_job_status(user_id, job_id, JobStatus.FAILED.value, str(e))


# ==================== MAIN LOOP ====================

async def worker_loop():
    logger.info("Worker loop started. Polling for RUNNING jobs...")

    while RUNNING:
        try:
            # 1. Wake sleeping accounts
            woken = wake_sleeping_accounts()
            if woken > 0:
                logger.info(f"Woke up {woken} sleeping account(s)")

            # 2. Get all active jobs
            jobs = get_active_jobs()
            running_jobs = [j for j in jobs if j.get("status") == JobStatus.RUNNING.value]

            for job in running_jobs:
                job_id = job["job_id"]

                # Already running?
                if job_id in CURRENT_TASKS and not CURRENT_TASKS[job_id].done():
                    continue

                # Spawn new task
                task = asyncio.create_task(run_job(job))
                CURRENT_TASKS[job_id] = task
                logger.info(f"Spawned task for job {job_id}")

            # 3. Cleanup finished tasks
            finished = [jid for jid, t in CURRENT_TASKS.items() if t.done()]
            for jid in finished:
                del CURRENT_TASKS[jid]

            await asyncio.sleep(7)  # Poll interval

        except Exception as e:
            logger.exception(f"Worker loop error: {e}")
            await asyncio.sleep(15)

    # Graceful shutdown
    logger.info("Shutting down worker...")
    for task in CURRENT_TASKS.values():
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
        logger.info("Interrupted by user")