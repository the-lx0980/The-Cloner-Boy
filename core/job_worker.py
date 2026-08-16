# core/job_worker.py
#
# A background loop that polls MongoDB for jobs with status "running"
# and actually forwards them, using your existing forward_messages() engine.
#
# One job runs at a time per job_id (tracked in RUNNING_JOB_TASKS) so pressing
# Start twice doesn't launch it twice, and Pause/Stop can cancel the task.

import asyncio
import logging

from database import (
    get_active_jobs, get_job, get_target, get_user_accounts,
    get_account, update_job, JobStatus
)
from core.forwarder import forward_messages

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 5

# job_id -> asyncio.Task, so we can avoid double-starting / can cancel on pause/stop
RUNNING_JOB_TASKS: dict[str, asyncio.Task] = {}


async def job_worker_loop(client):
    """
    Call this once at bot startup: asyncio.create_task(job_worker_loop(app))
    """
    logger.info("Job worker started.")
    while True:
        try:
            jobs = get_active_jobs()  # all jobs with status == "running", across users
            for job in jobs:
                job_id = job["job_id"]
                # Skip if already being executed
                task = RUNNING_JOB_TASKS.get(job_id)
                if task and not task.done():
                    continue
                # Launch it
                RUNNING_JOB_TASKS[job_id] = asyncio.create_task(
                    run_single_job(client, job)
                )
        except Exception:
            logger.exception("Job worker poll iteration failed")

        await asyncio.sleep(POLL_INTERVAL_SECONDS)


async def run_single_job(client, job: dict):
    user_id = job["user_id"]
    job_id = job["job_id"]

    try:
        for target_chat_id in job.get("target_chat_ids", []):
            # Re-fetch job each loop in case it was paused/stopped mid-run
            fresh = get_job(user_id, job_id)
            if not fresh or fresh.get("status") != JobStatus.RUNNING.value:
                logger.info(f"Job {job_id} no longer running, stopping.")
                return

            target = get_target(user_id, target_chat_id)
            if not target:
                continue

            if job.get("method") == "bot":
                # Forwarding via the main client (or a dedicated bot client if you
                # spin one up per forward_bot — for now this uses the main app client).
                exec_client = client
            else:
                # method == "user": pick an account and build a Pyrogram client from
                # its stored session_string. Simple sequential strategy for now.
                account_ids = job.get("account_ids") or []
                exec_client = None
                for acc_id in account_ids:
                    account = get_account(user_id, acc_id)
                    if not account or account.get("status") != "active":
                        continue
                    exec_client = await _get_account_client(account)
                    if exec_client:
                        break
                if exec_client is None:
                    logger.warning(f"Job {job_id}: no available account, pausing job.")
                    update_job(user_id, job_id, {"status": JobStatus.PAUSED.value})
                    return

            stats = await forward_messages(
                client=exec_client,
                user_id=user_id,
                source_chat_id=job.get("source_chat_id"),
                target=target,
                last_msg_id=job.get("last_msg_id", 0),
                skip=job.get("current_msg_id", job.get("skip", 0)),
                job_id=job_id,
            )

            # Persist progress
            update_job(user_id, job_id, {
                "current_msg_id": job.get("skip", 0) + stats.fetched,
            })

        # All targets done -> mark completed (unless future_new_posts should keep it alive)
        if not job.get("future_new_posts"):
            update_job(user_id, job_id, {"status": JobStatus.COMPLETED.value})

    except Exception:
        logger.exception(f"Job {job_id} crashed")
        update_job(user_id, job_id, {"status": JobStatus.FAILED.value})
    finally:
        RUNNING_JOB_TASKS.pop(job_id, None)


# ------------------------------------------------------------------
# Turns a stored user-account session_string into a connected Pyrogram
# Client, so the worker can forward through a real Telegram user account
# instead of the bot. Cache these so we don't reconnect every poll.
# ------------------------------------------------------------------
_ACCOUNT_CLIENTS: dict[str, "Client"] = {}


async def _get_account_client(account: dict):
    from pyrogram import Client
    from config import Config

    acc_id = account["account_id"]
    if acc_id in _ACCOUNT_CLIENTS:
        return _ACCOUNT_CLIENTS[acc_id]

    session_string = account.get("session_string")
    if not session_string:
        return None

    try:
        acc_client = Client(
            name=f"acc_{acc_id}",
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            session_string=session_string,
            in_memory=True,
        )
        await acc_client.start()
        _ACCOUNT_CLIENTS[acc_id] = acc_client
        return acc_client
    except Exception:
        logger.exception(f"Failed to start client for account {acc_id}")
        return None