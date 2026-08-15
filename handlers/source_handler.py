# handlers/source_handler.py
# Improved - Connected to new Job System

import re
import logging
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatType

from database import (
    is_admin, ensure_user, get_user_targets, get_target,
    get_user_accounts, get_user_bots, create_job
)
from handlers.keyboards import targets_list_keyboard

logger = logging.getLogger(__name__)

# Legacy flags (sirf quick forward ke liye)
CANCEL_FLAGS = {}
FORWARDING = {}


def build_source_options_keyboard(source_chat_id, last_msg_id: int) -> InlineKeyboardMarkup:
    """Source detect hone ke baad options"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📋 Create Job (Recommended)",
                callback_data=f"src:create_job:{source_chat_id}:{last_msg_id}"
            )
        ],
        [
            InlineKeyboardButton(
                "⚡ Quick Forward (Legacy)",
                callback_data=f"src:quick:{source_chat_id}:{last_msg_id}"
            )
        ],
        [
            InlineKeyboardButton("❌ Cancel", callback_data="src:cancel")
        ]
    ])


# ============================================================
# 1. Detect Source
# ============================================================

@Client.on_message(
    filters.private
    & filters.incoming
    & (
        filters.forwarded
        | filters.regex(
            r"(https?://)?(t\.me|telegram\.me|telegram\.dog)/(c/)?([a-zA-Z0-9_]+|\d+)/(\d+)"
        )
    )
)
async def source_detector(client: Client, message: Message):
    user_id = message.from_user.id

    if not is_admin(user_id):
        return await message.reply("❌ You are not allowed to use this bot.")

    # Clear any existing state
    client.job_create_state = getattr(client, "job_create_state", {})
    client.job_create_state[user_id] = None

    ensure_user(user_id)

    source_chat_id = None
    last_msg_id = None

    # Case 1: Text Link
    if message.text and not message.forward_from_chat:
        regex = re.compile(
            r"(https?://)?(t\.me|telegram\.me|telegram\.dog)/(c/)?([a-zA-Z0-9_]+|\d+)/(\d+)"
        )
        match = regex.search(message.text)
        if not match:
            return await message.reply("❌ Invalid Telegram message link.")

        chat_part = match.group(4)
        last_msg_id = int(match.group(5))

        if chat_part.isdigit():
            source_chat_id = int(f"-100{chat_part}")
        else:
            source_chat_id = chat_part

    # Case 2: Forwarded Message
    elif message.forward_from_chat:
        chat = message.forward_from_chat
        if chat.type not in [ChatType.CHANNEL, ChatType.GROUP, ChatType.SUPERGROUP]:
            return await message.reply("❌ I can only forward from Channels and Groups.")

        source_chat_id = chat.username or chat.id
        last_msg_id = message.forward_from_message_id
    else:
        return

    # Validate source
    try:
        source_chat = await client.get_chat(source_chat_id)
    except Exception as e:
        return await message.reply(f"❌ Cannot access source chat.\nError: `{e}`")

    if source_chat.type not in [ChatType.CHANNEL, ChatType.GROUP, ChatType.SUPERGROUP]:
        return await message.reply("❌ Source must be a Channel or Group.")

    targets = get_user_targets(user_id)
    if not targets:
        return await message.reply(
            "❌ You have no targets set.\n"
            "Add a target first using Dashboard → 🎯 Targets"
        )

    text = (
        f"**📥 Source Detected**\n\n"
        f"**Chat:** {source_chat.title}\n"
        f"**ID:** `{source_chat.id}`\n"
        f"**Last Message ID:** `{last_msg_id}`\n\n"
        f"Kya karna chahte ho?"
    )

    await message.reply(
        text,
        reply_markup=build_source_options_keyboard(source_chat.id, last_msg_id)
    )


# ============================================================
# 2. Source Options Callbacks
# ============================================================

@Client.on_callback_query(filters.regex(r"^src:"))
async def source_options_callback(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    if not is_admin(user_id):
        return await query.answer("Not allowed", show_alert=True)

    data = query.data

    if data == "src:cancel":
        await query.message.edit_text("❌ Cancelled.")
        return await query.answer()

    # ---------- Create Job (New System) ----------
    if data.startswith("src:create_job:"):
        parts = data.split(":")
        try:
            source_chat_id = int(parts[2]) if parts[2].lstrip("-").isdigit() else parts[2]
            last_msg_id = int(parts[3])
        except Exception:
            return await query.answer("Invalid data", show_alert=True)

        # Clear any existing state first
        client.job_create_state = getattr(client, "job_create_state", {})
        client.job_create_state[user_id] = None

        # Save state for job creation wizard
        client.job_create_state[user_id] = {
            "step": "select_targets",
            "source_chat_id": source_chat_id,
            "source_title": "Detected Source",
            "last_msg_id": last_msg_id,
            "selected_targets": []
        }

        targets = get_user_targets(user_id)

        from handlers.keyboards import select_targets_keyboard

        await query.message.edit_text(
            "**📋 Create Job – Select Targets**\n\n"
            "Kaunse targets par forward karna hai?\n"
            "Multiple select kar sakte ho:",
            reply_markup=select_targets_keyboard(targets, [])
        )
        return await query.answer()

    # ---------- Quick Forward (Legacy) ----------
    if data.startswith("src:quick:"):
        parts = data.split(":")
        try:
            source_chat_id = int(parts[2]) if parts[2].lstrip("-").isdigit() else parts[2]
            last_msg_id = int(parts[3])
        except Exception:
            return await query.answer("Invalid data", show_alert=True)

        targets = get_user_targets(user_id)

        buttons = []
        for t in targets:
            title = (t.get("title") or "Unknown")[:25]
            buttons.append([
                InlineKeyboardButton(
                    f"🎯 {title}",
                    callback_data=f"fwd:to:{t['chat_id']}:{source_chat_id}:{last_msg_id}"
                )
            ])

        if len(targets) > 1:
            buttons.append([
                InlineKeyboardButton(
                    "📤 Send to All",
                    callback_data=f"fwd:all:{source_chat_id}:{last_msg_id}"
                )
            ])

        buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="src:cancel")])

        await query.message.edit_text(
            "**⚡ Quick Forward (Legacy)**\n\n"
            "Select target:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return await query.answer()


# ============================================================
# 3. Legacy Quick Forward Callbacks (purana code)
# ============================================================

@Client.on_callback_query(filters.regex(r"^fwd:"))
async def forward_callbacks(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    if not is_admin(user_id):
        return await query.answer("Not allowed", show_alert=True)

    data = query.data

    # Clear any existing job create state
    client.job_create_state = getattr(client, "job_create_state", {})
    client.job_create_state[user_id] = None

    if data == "fwd:cancel":
        await query.message.edit_text("❌ Cancelled.")
        return await query.answer()

    if FORWARDING.get(user_id):
        return await query.answer("Already running. Send cancel first.", show_alert=True)

    if data.startswith("fwd:to:"):
        parts = data.split(":")
        try:
            target_chat_id = int(parts[2])
            source_chat_id = int(parts[3]) if parts[3].lstrip("-").isdigit() else parts[3]
            last_msg_id = int(parts[4])
        except Exception:
            return await query.answer("Invalid data", show_alert=True)

        target = get_target(user_id, target_chat_id)
        if not target:
            return await query.answer("Target not found", show_alert=True)

        await query.message.edit_text(
            f"**⏭ Skip Messages**\n\n"
            f"**Target:** {target.get('title')}\n"
            f"**Source:** `{source_chat_id}`\n"
            f"**Last Message ID:** `{last_msg_id}`\n\n"
            f"Kitne messages skip karna hai?\n"
            f"Example: `0` ya `100`\n\n"
            f"Number bhejo:"
        )

        client.forward_state = getattr(client, "forward_state", {})
        client.forward_state[user_id] = {
            "action": "waiting_skip",
            "target_chat_id": target_chat_id,
            "source_chat_id": source_chat_id,
            "last_msg_id": last_msg_id
        }
        return await query.answer()

    if data.startswith("fwd:all:"):
        parts = data.split(":")
        try:
            source_chat_id = int(parts[2]) if parts[2].lstrip("-").isdigit() else parts[2]
            last_msg_id = int(parts[3])
        except Exception:
            return await query.answer("Invalid data", show_alert=True)

        await query.message.edit_text(
            f"**⏭ Skip Messages (All Targets)**\n\n"
            f"Kitne messages skip karna hai?\n"
            f"Number bhejo (0 = no skip):"
        )

        client.forward_state = getattr(client, "forward_state", {})
        client.forward_state[user_id] = {
            "action": "waiting_skip_all",
            "source_chat_id": source_chat_id,
            "last_msg_id": last_msg_id
        }
        return await query.answer()


# ============================================================
# 4. Cancel
# ============================================================

@Client.on_message(filters.private & filters.regex(r"(?i)^cancel$"))
async def cancel_forward(client: Client, message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return

    if FORWARDING.get(user_id):
        CANCEL_FLAGS[user_id] = True
        await message.reply("🛑 Cancellation requested...")
    else:
        await message.reply("ℹ️ No active process.")
