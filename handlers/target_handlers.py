# handlers/target_handlers.py

from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery
from pyrogram.enums import ChatType
from pyrogram.errors import FloodWait
from bot import app
from database import (
    ensure_user, is_admin, add_target, get_user_targets,
    get_target, delete_target, update_target_settings
)
from handlers.keyboards import (
    targets_list_keyboard, target_settings_keyboard,
    confirm_delete_keyboard
)
import logging

logger = logging.getLogger(__name__)


# ==================== COMMANDS ====================

@Client.on_message(filters.private & filters.command("targets"))
async def cmd_targets(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return await message.reply("❌ You are not allowed to use this bot.")

    ensure_user(message.from_user.id)
    targets = get_user_targets(message.from_user.id)

    if not targets:
        text = (
            "**🎯 Your Targets**\n\n"
            "You have no targets yet.\n"
            "Click **Add Target** to add your first channel/group."
        )
    else:
        text = f"**🎯 Your Targets** ({len(targets)})\n\nSelect a target to manage settings:"

    await message.reply(text, reply_markup=targets_list_keyboard(targets))


@Client.on_message(filters.private & filters.command("addtarget"))
async def cmd_add_target(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return await message.reply("❌ You are not allowed to use this bot.")

    await message.reply(
        "**➕ Add New Target**\n\n"
        "Send me the **Channel / Group ID** or **Username**.\n\n"
        "Example:\n"
        "`-1001234567890`\n"
        "or\n"
        "`@mychannel`"
    )


# ==================== CALLBACKS ====================

@Client.on_callback_query(filters.regex(r"^tg:"))
async def target_callbacks(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    if not is_admin(user_id):
        return await query.answer("Not allowed", show_alert=True)

    data = query.data
    ensure_user(user_id)

    # -------- List / Refresh --------
    if data == "tg:list":
        targets = get_user_targets(user_id)
        text = f"**🎯 Your Targets** ({len(targets)})\n\nSelect a target to manage settings:"
        if not targets:
            text = "**🎯 Your Targets**\n\nNo targets found. Click Add Target."
        await query.message.edit_text(text, reply_markup=targets_list_keyboard(targets))
        return await query.answer()

    # -------- Add Target --------
    if data == "tg:add":
        await query.message.edit_text(
            "**➕ Add New Target**\n\n"
            "Send me the **Channel / Group ID** or **Username**.\n\n"
            "Example:\n`-1001234567890`  or  `@mychannel`\n\n"
            "Type /cancel to cancel."
        )
        # Store state (simple way using a dict or you can use a better FSM later)
        client.target_add_state = getattr(client, "target_add_state", {})
        client.target_add_state[user_id] = True
        return await query.answer()

    # -------- Open Target Settings --------
    if data.startswith("tg:open:"):
        chat_id = int(data.split(":")[2])
        target = get_target(user_id, chat_id)
        if not target:
            await query.answer("Target not found", show_alert=True)
            return

        title = target.get("title", "Unknown")
        text = (
            f"**🎯 Target Settings**\n\n"
            f"**Name:** {title}\n"
            f"**Chat ID:** `{chat_id}`\n\n"
            f"Configure all features below:"
        )
        await query.message.edit_text(text, reply_markup=target_settings_keyboard(target))
        return await query.answer()

    # -------- Delete Target (confirm) --------
    if data.startswith("tg:delete:"):
        chat_id = int(data.split(":")[2])
        target = get_target(user_id, chat_id)
        if not target:
            return await query.answer("Target not found", show_alert=True)

        await query.message.edit_text(
            f"**⚠️ Delete Target?**\n\n"
            f"**{target.get('title')}** (`{chat_id}`)\n\n"
            f"This will also delete all duplicate records of this target.\n"
            f"This action cannot be undone.",
            reply_markup=confirm_delete_keyboard(chat_id)
        )
        return await query.answer()

    # -------- Confirm Delete --------
    if data.startswith("tg:confirm_delete:"):
        chat_id = int(data.split(":")[2])
        success = delete_target(user_id, chat_id)
        if success:
            await query.answer("✅ Target deleted", show_alert=True)
            targets = get_user_targets(user_id)
            text = f"**🎯 Your Targets** ({len(targets)})"
            await query.message.edit_text(text, reply_markup=targets_list_keyboard(targets))
        else:
            await query.answer("Failed to delete", show_alert=True)
        return
