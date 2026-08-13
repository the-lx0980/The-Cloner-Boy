# handlers/text_input_handlers.py

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ChatType

from database import is_admin, update_target_settings, get_target
from handlers.keyboards import target_settings_keyboard, simple_back_keyboard
import logging

logger = logging.getLogger(__name__)


@Client.on_message(filters.private & filters.text & ~filters.command(["start", "targets", "addtarget", "cancel"]))
async def handle_settings_input(client: Client, message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return

    state = getattr(client, "settings_state", {}).get(user_id)
    add_state = getattr(client, "target_add_state", {}).get(user_id)

    # ---------- Add Target ----------
    if add_state:
        text = message.text.strip()
        try:
            if text.startswith("@"):
                chat = await client.get_chat(text)
            else:
                chat_id = int(text)
                chat = await client.get_chat(chat_id)

          
            # Check if the chat is NOT a channel, supergroup, or group
            if chat.type not in [ChatType.CHANNEL, ChatType.SUPERGROUP, ChatType.GROUP]:
                return await message.reply("❌ Only Channels and Groups are supported.")
    

            from database import add_target
            result = add_target(
                user_id=user_id,
                chat_id=chat.id,
                title=chat.title or "Unknown",
                username=chat.username
            )

            # clear state
            client.target_add_state[user_id] = False

            if result is None:
                return await message.reply("⚠️ This target is already added.")

            await message.reply(
                f"✅ **Target Added Successfully!**\n\n"
                f"**Name:** {chat.title}\n"
                f"**ID:** `{chat.id}`"
            )
            # show targets list
            from database import get_user_targets
            from handlers.keyboards import targets_list_keyboard
            targets = get_user_targets(user_id)
            await message.reply(
                f"**🎯 Your Targets** ({len(targets)})",
                reply_markup=targets_list_keyboard(targets)
            )

        except Exception as e:
            await message.reply(f"❌ Error: `{e}`\n\nPlease send a valid Chat ID or @username.")
        return

    # ---------- Settings Values ----------
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

        # clear state + show settings again
        client.settings_state[user_id] = None
        target = get_target(user_id, chat_id)
        if target:
            title = target.get("title", "Unknown")
            await message.reply(
                f"**🎯 Target Settings**\n\n**Name:** {title}\n**Chat ID:** `{chat_id}`",
                reply_markup=target_settings_keyboard(target)
            )

    except Exception as e:
        await message.reply(f"❌ Error: `{e}`")
