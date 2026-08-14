# handlers/jobs_handlers.py
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery

from database import (
    is_admin, ensure_user, get_user_jobs, get_job,
    set_job_status, delete_job, JobStatus
)
from handlers.keyboards import (
    jobs_list_keyboard, job_detail_keyboard,
    confirm_delete_job_keyboard
)
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

    if data == "job:list":
        await show_jobs_list(client, query)
        return

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

    if data.startswith("job:start:"):
        job_id = data.split(":")[2]
        job = get_job(user_id, job_id)
        if not job:
            return await query.answer("Job not found", show_alert=True)

        if job.get("status") == JobStatus.RUNNING.value:
            return await query.answer("Job is already running", show_alert=True)

        set_job_status(user_id, job_id, JobStatus.RUNNING.value)
        await query.answer("Job started (worker will pick it up)", show_alert=True)

        job = get_job(user_id, job_id)
        await query.message.edit_text(
            f"**📋 Job started**\n\nStatus: `running`",
            reply_markup=job_detail_keyboard(job)
        )
        return

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