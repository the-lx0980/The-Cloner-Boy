# handlers/source_handler.py

import re
import logging
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatType, MessageMediaType


from database import is_admin, get_user_targets, get_target, ensure_user
from core.forwarder import forward_messages
from handlers.keyboards import targets_list_keyboard

logger = logging.getLogger(__name__)

# Global cancel flags  {user_id: bool}
CANCEL_FLAGS = {}
# Currently running forwards  {user_id: bool}
FORWARDING = {}


def build_target_selector_keyboard(targets: list, source_chat_id, last_msg_id: int) -> InlineKeyboardMarkup:
    """
    Keyboard to select which target to forward to.
    We encode source info in callback_data carefully (length limit).
    """
    buttons = []

    for t in targets:
        title = (t.get("title") or "Unknown")[:25]
        chat_id = t["chat_id"]
        buttons.append([
            InlineKeyboardButton(
                f"🎯 {title}",
                callback_data=f"fwd:to:{chat_id}:{source_chat_id}:{last_msg_id}"
            )
        ])

    # Optional: Send to all
    if len(targets) > 1:
        buttons.append([
            InlineKeyboardButton(
                "📤 Send to All Targets",
                callback_data=f"fwd:all:{source_chat_id}:{last_msg_id}"
            )
        ])

    buttons.append([
        InlineKeyboardButton("❌ Cancel", callback_data="fwd:cancel")
    ])

    return InlineKeyboardMarkup(buttons)


# ============================================================
# 1. Detect Source (Link or Forwarded Message)
# ============================================================

@app.on_message(
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

    ensure_user(user_id)

    # Prevent multiple simultaneous forwards
    if FORWARDING.get(user_id):
        return await message.reply("⚠️ Please wait until the current forwarding process finishes.\nSend `cancel` to stop it.")

    source_chat_id = None
    last_msg_id = None

    # ---------- Case 1: Text Link ----------
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
            # Private channel/group → -100xxxxxxxxxx
            source_chat_id = int(f"-100{chat_part}")
        else:
            source_chat_id = chat_part  # username

    # ---------- Case 2: Forwarded Message ----------
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

    # Get user targets
    targets = get_user_targets(user_id)
    if not targets:
        return await message.reply(
            "❌ You have no targets set.\n"
            "Add a target first using /targets → ➕ Add Target"
        )

    # Show target selector
    text = (
        f"**📥 Source Detected**\n\n"
        f"**Chat:** {source_chat.title}\n"
        f"**ID:** `{source_chat.id}`\n"
        f"**Last Message ID:** `{last_msg_id}`\n\n"
        f"**Select Target Channel** to start forwarding:"
    )

    await message.reply(
        text,
        reply_markup=build_target_selector_keyboard(targets, source_chat.id, last_msg_id)
    )


# ============================================================
# 2. Target Selection Callbacks
# ============================================================

@app.on_callback_query(filters.regex(r"^fwd:"))
async def forward_callbacks(client: Client, query: CallbackQuery):
    user_id = query.from_user.id

    if not is_admin(user_id):
        return await query.answer("Not allowed", show_alert=True)

    data = query.data

    # Cancel
    if data == "fwd:cancel":
        await query.message.edit_text("❌ Forwarding cancelled by user.")
        return await query.answer()

    # Already forwarding?
    if FORWARDING.get(user_id):
        await query.answer("A process is already running. Send cancel first.", show_alert=True)
        return

    # -------- Send to ONE target --------
    if data.startswith("fwd:to:"):
        # callback_data = fwd:to:{target_chat_id}:{source_chat_id}:{last_msg_id}
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
            f"**🚀 Starting Forward...**\n\n"
            f"**Target:** {target.get('title')}\n"
            f"**Source ID:** `{source_chat_id}`\n"
            f"**Up to Message:** `{last_msg_id}`\n\n"
            f"Please wait..."
        )

        # Start forwarding
        FORWARDING[user_id] = True
        CANCEL_FLAGS[user_id] = False

        try:
            await forward_messages(
                client=client,
                user_id=user_id,
                source_chat_id=source_chat_id,
                target=target,
                last_msg_id=last_msg_id,
                skip=0,
                progress_message=query.message,
                cancel_flag=CANCEL_FLAGS
            )
        except Exception as e:
            logger.exception(e)
            await query.message.edit_text(f"**❌ Error during forwarding**\n\n`{e}`")
        finally:
            FORWARDING[user_id] = False
            CANCEL_FLAGS[user_id] = False

        return await query.answer()

    # -------- Send to ALL targets --------
    if data.startswith("fwd:all:"):
        parts = data.split(":")
        try:
            source_chat_id = int(parts[2]) if parts[2].lstrip("-").isdigit() else parts[2]
            last_msg_id = int(parts[3])
        except Exception:
            return await query.answer("Invalid data", show_alert=True)

        targets = get_user_targets(user_id)
        if not targets:
            return await query.answer("No targets", show_alert=True)

        await query.message.edit_text(
            f"**🚀 Starting Forward to ALL Targets**\n\n"
            f"Total Targets: `{len(targets)}`\n"
            f"Source: `{source_chat_id}`\n"
            f"Up to Message: `{last_msg_id}`\n\n"
            f"Processing one by one..."
        )

        FORWARDING[user_id] = True
        CANCEL_FLAGS[user_id] = False

        try:
            for idx, target in enumerate(targets, 1):
                if CANCEL_FLAGS.get(user_id):
                    await query.message.edit_text("**🛑 Cancelled by user**")
                    break

                await query.message.edit_text(
                    f"**🚀 Forwarding to Target {idx}/{len(targets)}**\n\n"
                    f"**Current:** {target.get('title')}\n"
                    f"Source: `{source_chat_id}`"
                )

                await forward_messages(
                    client=client,
                    user_id=user_id,
                    source_chat_id=source_chat_id,
                    target=target,
                    last_msg_id=last_msg_id,
                    skip=0,
                    progress_message=query.message,
                    cancel_flag=CANCEL_FLAGS
                )

            if not CANCEL_FLAGS.get(user_id):
                await query.message.edit_text(
                    f"**✅ Completed for all {len(targets)} targets!**"
                )

        except Exception as e:
            logger.exception(e)
            await query.message.edit_text(f"**❌ Error**\n\n`{e}`")
        finally:
            FORWARDING[user_id] = False
            CANCEL_FLAGS[user_id] = False

        return await query.answer()


# ============================================================
# 3. Cancel Command / Message
# ============================================================

@app.on_message(filters.private & filters.regex(r"(?i)^cancel$"))
async def cancel_forward(client: Client, message: Message):
    user_id = message.from_user.id

    if not is_admin(user_id):
        return

    if FORWARDING.get(user_id):
        CANCEL_FLAGS[user_id] = True
        await message.reply("🛑 **Cancellation requested.**\nWaiting for current message to finish...")
    else:
        await message.reply("ℹ️ No active forwarding process found.")
