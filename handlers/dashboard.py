# handlers/dashboard.py
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery
from pyrogram.enums import ParseMode

from database import is_admin, ensure_user, get_dashboard_counts
from handlers.keyboards import dashboard_keyboard
import logging

logger = logging.getLogger(__name__)


def build_dashboard_text(user_id: int) -> str:
    counts = get_dashboard_counts(user_id)
    return (
        "╭────────────────────────╮\n"
        "│     📊 **Dashboard**      │\n"
        "├────────────────────────┤\n"
        f"│ 🎯 Targets: **{counts['targets']}**\n"
        f"│ 👤 Accounts: **{counts['accounts']}**\n"
        f"│ 🤖 Forward Bots: **{counts['bots']}**\n"
        f"│ 📋 Active Jobs: **{counts['active_jobs']}**\n"
        f"│ 🛡 Duplicates: **{counts['duplicates']:,}**\n"
        "╰────────────────────────╯\n\n"
        "Select an option below:"
    )


@Client.on_message(filters.private & filters.command("start"))
async def cmd_start(client: Client, message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return await message.reply("❌ You are not allowed to use this bot.")

    ensure_user(user_id)
    text = build_dashboard_text(user_id)
    await message.reply(text, reply_markup=dashboard_keyboard(), parse_mode=ParseMode.MARKDOWN)


@Client.on_callback_query(filters.regex(r"^dash:"))
async def dashboard_callbacks(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    if not is_admin(user_id):
        return await query.answer("Not allowed", show_alert=True)

    data = query.data

    if data in ["dash:home", "dash:refresh"]:
        text = build_dashboard_text(user_id)
        await query.message.edit_text(text, reply_markup=dashboard_keyboard(), parse_mode=ParseMode.MARKDOWN)
        return await query.answer()

    if data == "dash:targets":
        from handlers.target_handlers import cmd_targets_internal
        await cmd_targets_internal(client, query)
        return

    if data == "dash:accounts":
        from handlers.accounts_handlers import show_accounts_list
        await show_accounts_list(client, query)
        return

    if data == "dash:bots":
        from handlers.bots_handlers import show_bots_list
        await show_bots_list(client, query)
        return

    if data == "dash:jobs":
        from handlers.jobs_handlers import show_jobs_list
        await show_jobs_list(client, query)
        return

    if data == "dash:stats":
        counts = get_dashboard_counts(user_id)
        text = (
            "**📊 Statistics Overview**\n\n"
            f"🎯 Targets: `{counts['targets']}`\n"
            f"👤 Accounts: `{counts['accounts']}`\n"
            f"🤖 Bots: `{counts['bots']}`\n"
            f"📋 Active Jobs: `{counts['active_jobs']}`\n"
            f"🛡 Total Duplicates Tracked: `{counts['duplicates']:,}`\n\n"
            "More detailed stats are available inside each section."
        )
        await query.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("« Back", callback_data="dash:home")]
            ])
        )
        return await query.answer()

    if data == "dash:settings":
        await query.answer("Global settings coming soon", show_alert=True)
        return