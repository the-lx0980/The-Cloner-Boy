# handlers/text_input_handlers.py

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ChatType
import logging

from database import is_admin, update_target_settings, get_target, get_user_targets, add_target
from handlers.keyboards import target_settings_keyboard, targets_list_keyboard

logger = logging.getLogger(__name__)


@Client.on_message(filters.private & filters.text & ~filters.command(["start", "targets", "addtarget", "cancel"]))
async def handle_settings_input(client: Client, message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return

    # ============================================================
    # 1. FORWARD SKIP NUMBER (Highest Priority)
    # ============================================================
    forward_state = getattr(client, "forward_state", {}).get(user_id)

    if forward_state and forward_state.get("action") in ["waiting_skip", "waiting_skip_all"]:
        try:
            skip = int(message.text.strip())
            if skip < 0:
                return await message.reply("❌ Skip number 0 se kam nahi ho sakta.")
        except ValueError:
            return await message.reply("❌ Sirf number bhejo.\nExample: `0` ya `150`")

        source_chat_id = forward_state["source_chat_id"]
        last_msg_id = forward_state["last_msg_id"]

        if skip >= last_msg_id:
            return await message.reply(
                f"❌ Skip number `{last_msg_id}` se kam hona chahiye."
            )

        # Clear state
        client.forward_state[user_id] = None

        # Import here to avoid circular import
        from handlers.source_handler import FORWARDING, CANCEL_FLAGS
        from core.forwarder import forward_messages

        if forward_state["action"] == "waiting_skip":
            target_chat_id = forward_state["target_chat_id"]
            target = get_target(user_id, target_chat_id)

            if not target:
                return await message.reply("❌ Target not found.")

            msg = await message.reply(
                f"**🚀 Starting Forward...**\n\n"
                f"**Target:** {target.get('title')}\n"
                f"**Skip:** `{skip}` messages\n"
                f"**Up to Message:** `{last_msg_id}`\n\n"
                f"Please wait..."
            )

            FORWARDING[user_id] = True
            CANCEL_FLAGS[user_id] = False

            try:
                await forward_messages(
                    client=client,
                    user_id=user_id,
                    source_chat_id=source_chat_id,
                    target=target,
                    last_msg_id=last_msg_id,
                    skip=skip,
                    progress_message=msg,
                    cancel_flag=CANCEL_FLAGS
                )
            except Exception as e:
                logger.exception(e)
                await msg.edit_text(f"**❌ Error during forwarding**\n\n`{e}`")
            finally:
                FORWARDING[user_id] = False
                CANCEL_FLAGS[user_id] = False

        elif forward_state["action"] == "waiting_skip_all":
            targets = get_user_targets(user_id)
            if not targets:
                return await message.reply("❌ No targets found.")

            msg = await message.reply(
                f"**🚀 Starting Forward to ALL Targets**\n\n"
                f"**Skip:** `{skip}`\n"
                f"**Total Targets:** `{len(targets)}`\n\n"
                f"Processing..."
            )

            FORWARDING[user_id] = True
            CANCEL_FLAGS[user_id] = False

            try:
                for idx, target in enumerate(targets, 1):
                    if CANCEL_FLAGS.get(user_id):
                        await msg.edit_text("**🛑 Cancelled by user**")
                        break

                    await msg.edit_text(
                        f"**🚀 Forwarding to Target {idx}/{len(targets)}**\n\n"
                        f"**Current:** {target.get('title')}\n"
                        f"**Skip:** `{skip}`"
                    )

                    await forward_messages(
                        client=client,
                        user_id=user_id,
                        source_chat_id=source_chat_id,
                        target=target,
                        last_msg_id=last_msg_id,
                        skip=skip,
                        progress_message=msg,
                        cancel_flag=CANCEL_FLAGS
                    )

                if not CANCEL_FLAGS.get(user_id):
                    await msg.edit_text(
                        f"**✅ Completed for all {len(targets)} targets!**"
                    )

            except Exception as e:
                logger.exception(e)
                await msg.edit_text(f"**❌ Error**\n\n`{e}`")
            finally:
                FORWARDING[user_id] = False
                CANCEL_FLAGS[user_id] = False

        return   # Important: aage mat jao

    # ============================================================
    # 2. ADD TARGET
    # ============================================================
    add_state = getattr(client, "target_add_state", {}).get(user_id)

    if add_state:
        text = message.text.strip()
        try:
            if text.startswith("@"):
                chat = await client.get_chat(text)
            else:
                chat_id = int(text)
                chat = await client.get_chat(chat_id)

            if chat.type not in [ChatType.CHANNEL, ChatType.SUPERGROUP, ChatType.GROUP]:
                return await message.reply("❌ Only Channels and Groups are supported.")

            result = add_target(
                user_id=user_id,
                chat_id=chat.id,
                title=chat.title or "Unknown",
                username=getattr(chat, "username", None)
            )

            client.target_add_state[user_id] = False

            if result is None:
                return await message.reply("⚠️ This target is already added.")

            await message.reply(
                f"✅ **Target Added Successfully!**\n\n"
                f"**Name:** {chat.title}\n"
                f"**ID:** `{chat.id}`"
            )

            targets = get_user_targets(user_id)
            await message.reply(
                f"**🎯 Your Targets** ({len(targets)})",
                reply_markup=targets_list_keyboard(targets)
            )

        except ValueError:
            await message.reply("❌ Invalid Chat ID. Please send a valid number or @username.")
        except Exception as e:
            await message.reply(
                f"❌ Error: `{e}`\n\n"
                f"Make sure:\n"
                f"• Bot is **Admin** in that channel/group\n"
                f"• You sent correct Chat ID or @username"
            )
        return

    # ============================================================
    # 3. SETTINGS VALUES
    # ============================================================
    state = getattr(client, "settings_state", {}).get(user_id)

    if not state:
        return

    action = state.get("action")
    chat_id = state.get("chat_id")
    text = message.text.strip()

    if text.lower() == "/cancel":
        client.settings_state[user_id] = None
        target = get_target(user_id, chat_id)
        if target:
            await message.reply(
                "**Cancelled.** Back to settings.",
                reply_markup=target_settings_keyboard(target)
            )
        return

    try:
        if action == "set_delay":
            delay = float(text)
            if delay < 0:
                return await message.reply("Delay cannot be negative.")
            update_target_settings(user_id, chat_id, {"delay": delay})
            await message.reply(f"✅ Delay set to **{delay}s**")

        elif action == "set_caption_template":
            update_target_settings(user_id, chat_id, {"caption_template": text})
            await message.reply("✅ Caption template updated.")

        elif action == "set_block_words":
            if text.lower() == "clear":
                words = []
            else:
                words = [w.strip() for w in text.split(",") if w.strip()]
            update_target_settings(user_id, chat_id, {"block_words": words})
            await message.reply(f"✅ Block words updated ({len(words)} words)")

        elif action == "set_whitelist":
            if text.lower() == "clear":
                words = []
            else:
                words = [w.strip() for w in text.split(",") if w.strip()]
            update_target_settings(user_id, chat_id, {"whitelist": words})
            await message.reply(f"✅ Whitelist updated ({len(words)} words)")

        elif action == "set_replacements":
            if text.lower() == "clear":
                reps = []
            else:
                reps = []
                for line in text.splitlines():
                    if "=>" in line:
                        left, right = line.split("=>", 1)
                        reps.append({"from": left.strip(), "to": right.strip()})
            update_target_settings(user_id, chat_id, {"replacements": reps})
            await message.reply(f"✅ Replacements updated ({len(reps)} rules)")

        elif action == "set_inline_buttons":
            if text.lower() == "clear":
                buttons = []
            else:
                buttons = []
                for line in text.splitlines():
                    row = []
                    for part in line.split("||"):
                        part = part.strip()
                        if " - " in part:
                            btn_text, btn_url = part.split(" - ", 1)
                            row.append({"text": btn_text.strip(), "url": btn_url.strip()})
                    if row:
                        buttons.append(row)
            update_target_settings(user_id, chat_id, {"inline_buttons": buttons})
            await message.reply(f"✅ Inline buttons updated ({len(buttons)} rows)")

        # Clear state + show settings again
        client.settings_state[user_id] = None
        target = get_target(user_id, chat_id)
        if target:
            title = target.get("title", "Unknown")
            await message.reply(
                f"**🎯 Target Settings**\n\n"
                f"**Name:** {title}\n"
                f"**Chat ID:** `{chat_id}`",
                reply_markup=target_settings_keyboard(target)
            )

    except Exception as e:
        await message.reply(f"❌ Error: `{e}`")
