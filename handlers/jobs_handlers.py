# handlers/jobs_handlers.py
# Updated with Permission Check

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery
from pyrogram import Client as TempClient

from config import Config
from database import (
    is_admin, ensure_user, get_user_jobs, get_job,
    set_job_status, delete_job, JobStatus,
    get_bot, get_next_available_account
)
from handlers.keyboards import (
    jobs_list_keyboard, job_detail_keyboard,
    confirm_delete_job_keyboard
)
from core.permissions import validate_job_permissions
from core.security import decrypt_session
import logging

logger = logging.getLogger(__name__)


async def show_jobs_list(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    jobs = get_user_jobs(user_id, limit=30)

    if not jobs:
        text = (
            "**📋 Forward Jobs**\n\n"
            "You have no jobs yet.\n"
            "Click **Create Job** to start a new forwarding task."
        )
    else:
        text = f"**📋 Forward Jobs** ({len(jobs)})\n\nSelect a job:"

    await query.message.edit_text(text, reply_markup=jobs_list_keyboard(jobs))
    await query.answer()


@Client.on_callback_query(filters.regex(r"^job:"))
async def jobs_callbacks(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    if not is_admin(user_id):
        return await query.answer("Not allowed", show_alert=True)

    data = query.data
    ensure_user(user_id)

    # -------------------- List --------------------
    if data == "job:list":
        await show_jobs_list(client, query)
        return

    # -------------------- Create Job --------------------
    if data == "job:create":
        await query.message.edit_text(
            "**📋 Create New Job – Step 1**\n\n"
            "Send the **Source Channel/Group** link or forward a message from it.\n\n"
            "Example:\n`https://t.me/c/1234567890/100`\n\n"
            "Type /cancel to cancel."
        )
        client.job_create_state = getattr(client, "job_create_state", {})
        client.job_create_state[user_id] = {"step": "source"}
        return await query.answer()

    # -------------------- Open Job --------------------
    if data.startswith("job:open:"):
        job_id = data.split(":")[2]
        job = get_job(user_id, job_id)
        if not job:
            return await query.answer("Job not found", show_alert=True)

        stats = job.get("stats", {})
        text = (
            f"**📋 Job Details**\n\n"
            f"**Name:** {job.get('name')}\n"
            f"**Status:** `{job.get('status')}`\n"
            f"**Source:** {job.get('source_title')} (`{job.get('source_chat_id')}`)\n"
            f"**Targets:** {len(job.get('target_chat_ids', []))}\n"
            f"**Method:** `{job.get('method')}`\n"
            f"**Future Posts:** `{'ON' if job.get('future_new_posts') else 'OFF'}`\n\n"
            f"**Progress:**\n"
            f"• Fetched: `{stats.get('fetched', 0)}`\n"
            f"• Forwarded: `{stats.get('forwarded', 0)}`\n"
            f"• Skipped (filter): `{stats.get('skipped_filter', 0)}`\n"
            f"• Duplicates: `{stats.get('skipped_duplicate', 0)}`\n"
            f"• Errors: `{stats.get('errors', 0)}`"
        )
        await query.message.edit_text(text, reply_markup=job_detail_keyboard(job))
        return await query.answer()

    # -------------------- START JOB (with Permission Check) --------------------
    if data.startswith("job:start:"):
        job_id = data.split(":")[2]
        job = get_job(user_id, job_id)
        if not job:
            return await query.answer("Job not found", show_alert=True)

        if job.get("status") == JobStatus.RUNNING.value:
            return await query.answer("Job is already running", show_alert=True)

        method = job.get("method")
        source_chat_id = job.get("source_chat_id")
        target_chat_ids = job.get("target_chat_ids", [])

        check_client = None
        try:
            # Create temporary client for permission check
            if method == "bot":
                bot = get_bot(user_id, job.get("bot_id"))
                if not bot or bot.get("status") != "active":
                    return await query.answer("Bot not available", show_alert=True)

                check_client = TempClient(
                    name=f"perm_check_{job_id}",
                    api_id=Config.API_ID,
                    api_hash=Config.API_HASH,
                    bot_token=bot["bot_token"],
                    in_memory=True,
                    no_updates=True
                )
                await check_client.start()

            elif method == "user":
                account = get_next_available_account(user_id, job.get("account_ids", []))
                if not account:
                    return await query.answer("No available account", show_alert=True)

                session = decrypt_session(account["session_string"])
                check_client = TempClient(
                    name=f"perm_check_{job_id}",
                    api_id=Config.API_ID,
                    api_hash=Config.API_HASH,
                    session_string=session,
                    in_memory=True,
                    no_updates=True
                )
                await check_client.start()
            else:
                return await query.answer("Unknown method", show_alert=True)

            # Run permission validation
            is_valid, msg = await validate_job_permissions(
                client=check_client,
                method=method,
                source_chat_id=source_chat_id,
                target_chat_ids=target_chat_ids
            )

            await check_client.stop()
            check_client = None

            if not is_valid:
                await query.answer("Permission Error", show_alert=True)
                await query.message.reply(
                    f"**❌ Permission Check Failed**\n\n"
                    f"`{msg}`\n\n"
                    f"**Rules Reminder:**\n"
                    f"• Private Source + Bot → Bot must be **Admin**\n"
                    f"• User Account → Must be **Member** of source\n"
                    f"• Target → Bot/Account must be **Admin**"
                )
                return

        except Exception as e:
            if check_client:
                try:
                    await check_client.stop()
                except:
                    pass
            logger.exception(e)
            await query.answer("Permission check failed", show_alert=True)
            await query.message.reply(f"❌ Permission check error:\n`{e}`")
            return

        # All good → Start Job
        set_job_status(user_id, job_id, JobStatus.RUNNING.value)
        await query.answer("✅ Job started (Permissions OK)", show_alert=True)

        job = get_job(user_id, job_id)
        await query.message.edit_text(
            f"**📋 Job started**\n\n"
            f"Status: `running`\n"
            f"Permissions: ✅ Passed",
            reply_markup=job_detail_keyboard(job)
        )
        return

    # -------------------- Pause --------------------
    if data.startswith("job:pause:"):
        job_id = data.split(":")[2]
        set_job_status(user_id, job_id, JobStatus.PAUSED.value)
        await query.answer("Job paused", show_alert=True)
        job = get_job(user_id, job_id)
        await query.message.edit_text(
            "**📋 Job paused**",
            reply_markup=job_detail_keyboard(job)
        )
        return

    # -------------------- Cancel --------------------
    if data.startswith("job:cancel:"):
        job_id = data.split(":")[2]
        set_job_status(user_id, job_id, JobStatus.CANCELLED.value)
        await query.answer("Job cancelled", show_alert=True)
        job = get_job(user_id, job_id)
        await query.message.edit_text(
            "**📋 Job cancelled**",
            reply_markup=job_detail_keyboard(job)
        )
        return

    # -------------------- Delete --------------------
    if data.startswith("job:delete:"):
        job_id = data.split(":")[2]
        job = get_job(user_id, job_id)
        if not job:
            return await query.answer("Job not found", show_alert=True)

        await query.message.edit_text(
            f"**⚠️ Delete Job?**\n\n"
            f"**{job.get('name')}**\n\n"
            f"This cannot be undone.",
            reply_markup=confirm_delete_job_keyboard(job_id)
        )
        return await query.answer()

    if data.startswith("job:confirm_delete:"):
        job_id = data.split(":")[2]
        success = delete_job(user_id, job_id)
        if success:
            await query.answer("✅ Job deleted", show_alert=True)
            await show_jobs_list(client, query)
        else:
            await query.answer("Failed to delete", show_alert=True)
        return
