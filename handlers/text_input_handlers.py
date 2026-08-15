# handlers/text_input_handlers.py
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ChatType, ParseMode
from pyrogram.errors import (
    PhoneCodeInvalid, PhoneCodeExpired, SessionPasswordNeeded,
    PhoneNumberInvalid, FloodWait
)
import logging
import re

from config import Config
from database import (
    is_admin, update_target_settings, get_target, get_user_targets,
    add_target, add_forward_bot, add_forward_account, update_account,
    create_job, get_user_accounts, get_user_bots, get_user_jobs
)
from handlers.keyboards import (
    target_settings_keyboard, targets_list_keyboard,
    accounts_list_keyboard, bots_list_keyboard, jobs_list_keyboard
)

logger = logging.getLogger(__name__)


@Client.on_message(filters.private & filters.text & ~filters.command(["start", "targets", "cancel"]))
async def handle_all_text_input(client: Client, message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return

    text = message.text.strip()

    # ============================================================
    # 1. CANCEL
    # ============================================================
    if text.lower() == "/cancel" or text.lower() == "cancel":
        # Clear all possible states
        for state_name in ["settings_state", "target_add_state", "account_add_state",
                           "account_edit_state", "bot_add_state", "job_create_state",
                           "forward_state"]:
            state = getattr(client, state_name, {})
            if user_id in state:
                # If there's a temp client in account_add_state, disconnect it
                if state_name == "account_add_state" and state[user_id]:
                    temp_client = state[user_id].get("temp_client")
                    if temp_client:
                        try:
                            await temp_client.disconnect()
                        except:
                            pass
                state[user_id] = None
        await message.reply("✅ Cancelled.")
        return

    # ============================================================
    # 2. ACCOUNT LOGIN FLOW (Phone → OTP → 2FA → Session)
    # ============================================================
    account_state = getattr(client, "account_add_state", {}).get(user_id)

    if account_state:
        step = account_state.get("step")

        # ---------- Step 1: Phone Number ----------
        if step == "phone":
            phone = text.strip()
            if not phone.startswith("+") or not phone[1:].isdigit():
                return await message.reply(
                    "❌ Invalid phone number.\n"
                    "Please send in international format.\n"
                    "Example: `+919876543210`"
                )

            try:
                # Create a temporary client just for login
                temp_client = Client(
                    name=f"login_{user_id}",
                    api_id=Config.API_ID,
                    api_hash=Config.API_HASH,
                    in_memory=True
                )
                await temp_client.connect()

                sent_code = await temp_client.send_code(phone)

                # Save state
                client.account_add_state[user_id] = {
                    "step": "otp",
                    "phone": phone,
                    "phone_code_hash": sent_code.phone_code_hash,
                    "temp_client": temp_client          # keep reference
                }

                await message.reply(
                    f"**📱 Code Sent!**\n\n"
                    f"A login code has been sent to `{phone}`.\n\n"
                    f"Please send the **OTP** code now.\n\n"
                    f"Type /cancel to cancel."
                )
            except PhoneNumberInvalid:
                await message.reply("❌ Invalid phone number.")
            except FloodWait as e:
                await message.reply(f"⏳ FloodWait: Please wait `{e.value}` seconds.")
            except Exception as e:
                logger.exception(e)
                await message.reply(f"❌ Error sending code: `{e}`")
            return

        # ---------- Step 2: OTP ----------
        if step == "otp":
            otp = text.strip().replace(" ", "")
            phone = account_state["phone"]
            phone_code_hash = account_state["phone_code_hash"]
            temp_client: Client = account_state["temp_client"]

            try:
                await temp_client.sign_in(
                    phone_number=phone,
                    phone_code_hash=phone_code_hash,
                    phone_code=otp
                )

                # Success → export session
                session_string = await temp_client.export_session_string()
                await temp_client.disconnect()

                # Save to database
                result = add_forward_account(
                    user_id=user_id,
                    phone=phone,
                    session_string=session_string,
                    name=phone
                )

                client.account_add_state[user_id] = None

                if result is None:
                    return await message.reply("⚠️ This phone number is already added.")

                await message.reply(
                    f"✅ **Account Added Successfully!**\n\n"
                    f"**Phone:** `{phone}`\n"
                    f"**Account ID:** `{result['account_id']}`\n\n"
                    f"You can now use this account for forwarding jobs."
                )

                accounts = get_user_accounts(user_id)
                await message.reply(
                    f"**👤 My Accounts** ({len(accounts)})",
                    reply_markup=accounts_list_keyboard(accounts)
                )

            except PhoneCodeInvalid:
                await message.reply("❌ Invalid OTP. Please try again.")
            except PhoneCodeExpired:
                await message.reply("❌ OTP expired. Please start again with /cancel and add account.")
                client.account_add_state[user_id] = None
                try:
                    await temp_client.disconnect()
                except:
                    pass
            except SessionPasswordNeeded:
                # 2FA is enabled
                client.account_add_state[user_id] = {
                    "step": "2fa",
                    "phone": phone,
                    "temp_client": temp_client
                }
                await message.reply(
                    "**🔐 Two-Step Verification Enabled**\n\n"
                    "Please send your **2FA password** now."
                )
            except Exception as e:
                logger.exception(e)
                await message.reply(f"❌ Login failed: `{e}`")
                client.account_add_state[user_id] = None
                try:
                    await temp_client.disconnect()
                except:
                    pass
            return

        # ---------- Step 3: 2FA Password ----------
        if step == "2fa":
            password = text.strip()
            temp_client: Client = account_state["temp_client"]
            phone = account_state["phone"]

            try:
                await temp_client.check_password(password)

                session_string = await temp_client.export_session_string()
                await temp_client.disconnect()

                result = add_forward_account(
                    user_id=user_id,
                    phone=phone,
                    session_string=session_string,
                    name=phone
                )

                client.account_add_state[user_id] = None

                if result is None:
                    return await message.reply("⚠️ This phone number is already added.")

                await message.reply(
                    f"✅ **Account Added Successfully (with 2FA)!**\n\n"
                    f"**Phone:** `{phone}`\n"
                    f"**Account ID:** `{result['account_id']}`"
                )

                accounts = get_user_accounts(user_id)
                await message.reply(
                    f"**👤 My Accounts** ({len(accounts)})",
                    reply_markup=accounts_list_keyboard(accounts)
                )

            except Exception as e:
                logger.exception(e)
                await message.reply(f"❌ 2FA failed: `{e}`\n\nPlease try again or /cancel.")
            return

    # ============================================================
    # 0. QUICK FORWARD – Skip number received -> actually start it
    # ============================================================
    fwd_state = getattr(client, "forward_state", {}).get(user_id)
    if fwd_state and fwd_state.get("action") in ("waiting_skip", "waiting_skip_all"):
        try:
            skip = int(text)
            if skip < 0:
                return await message.reply("❌ Skip cannot be negative.")
        except ValueError:
            return await message.reply("❌ Please send a number. Example: `0` or `100`")

        from core.forwarder import forward_messages
        from handlers.source_handler import FORWARDING, CANCEL_FLAGS
        from database import get_target, get_user_targets

        source_chat_id = fwd_state["source_chat_id"]
        last_msg_id = fwd_state["last_msg_id"]

        if fwd_state["action"] == "waiting_skip":
            targets = [get_target(user_id, fwd_state["target_chat_id"])]
        else:
            targets = get_user_targets(user_id)
        targets = [t for t in targets if t]

        client.forward_state[user_id] = None
        if not targets:
            return await message.reply("❌ Target not found.")

        FORWARDING[user_id] = True
        CANCEL_FLAGS[user_id] = False
        progress = await message.reply("**🚀 Starting forward...**")

        try:
            for target in targets:
                await forward_messages(
                    client=client, user_id=user_id,
                    source_chat_id=source_chat_id, target=target,
                    last_msg_id=last_msg_id, skip=skip,
                    progress_message=progress, cancel_flag=CANCEL_FLAGS,
                )
            await progress.edit_text("**✅ Forwarding finished.**")
        except Exception as e:
            logger.exception("Quick forward failed")
            await progress.edit_text(f"❌ Stopped due to an error:\n`{e}`")
        finally:
            FORWARDING[user_id] = False
        return
    # ============================================================
    # 3. ADD TARGET
    # ============================================================
    add_state = getattr(client, "target_add_state", {}).get(user_id)
    if add_state:
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
# 4. ADD FORWARD BOT (Fixed Version)
# ============================================================
    bot_add_state = getattr(client, "bot_add_state", {}).get(user_id)
    if bot_add_state:
        token = text.strip()

        # Basic format check
        if ":" not in token or len(token) < 40:
            return await message.reply(
                "❌ Invalid bot token format.\n\n"
                "Token looks like this:\n"
                "`123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw`"
            )

        try:
            # Better validation method
            from pyrogram import Client as TempClient

            temp_bot = TempClient(
                name=f"validate_{user_id}_{int(message.id)}",  # unique name
                api_id=Config.API_ID,
                api_hash=Config.API_HASH,
                bot_token=token,
                in_memory=True,
                no_updates=True
            )

            await temp_bot.start()          # start() better hai connect() se
            me = await temp_bot.get_me()
            await temp_bot.stop()

            bot_username = me.username
            bot_name = me.first_name or f"Bot {token[:8]}"

            # Save to database
            result = add_forward_bot(
                user_id=user_id,
                bot_token=token,
                bot_username=bot_username,
                name=bot_name
            )

            client.bot_add_state[user_id] = False

            if result is None:
                return await message.reply("⚠️ This bot token is already added.")

            await message.reply(
                f"✅ **Forward Bot Added Successfully!**\n\n"
                f"**Name:** {bot_name}\n"
                f"**Username:** @{bot_username}\n"
                f"**Bot ID:** `{result.get('bot_id')}`\n\n"
                f"Ab aap is bot ko Jobs mein use kar sakte ho."
            )

            bots = get_user_bots(user_id)
            await message.reply(
                f"**🤖 Forward Bots** ({len(bots)})",
                reply_markup=bots_list_keyboard(bots)
            )

        except Exception as e:
            error_msg = str(e).lower()

            if "auth_key_unregistered" in error_msg or "401" in error_msg:
                await message.reply(
                    "❌ **Invalid Bot Token**\n\n"
                    "Token galat hai ya expire ho gaya hai.\n"
                    "Naya token @BotFather se leke try karo."
                )
            elif "unauthorized" in error_msg or "token" in error_msg:
                await message.reply("❌ Invalid Bot Token. Please check and try again.")
            elif "flood" in error_msg:
                await message.reply("⏳ FloodWait! Thodi der baad try karein.")
            else:
                logger.exception(e)
                await message.reply(f"❌ Error adding bot:\n`{e}`")

            # Optional: state clear karna hai toh
            # client.bot_add_state[user_id] = False

        return    

    # ============================================================
    # 5. ACCOUNT EDIT (limit / sleep)
    # ============================================================
    account_edit = getattr(client, "account_edit_state", {}).get(user_id)
    if account_edit:
        action = account_edit.get("action")
        account_id = account_edit.get("account_id")

        try:
            if action == "set_limit":
                limit = int(text)
                if limit < 1:
                    return await message.reply("Limit must be at least 1.")
                update_account(user_id, account_id, {"forward_limit": limit})
                await message.reply(f"✅ Forward limit set to **{limit}**")

            elif action == "set_sleep":
                minutes = int(text)
                if minutes < 1:
                    return await message.reply("Sleep time must be at least 1 minute.")
                update_account(user_id, account_id, {"sleep_after_limit_minutes": minutes})
                await message.reply(f"✅ Sleep after limit set to **{minutes} minutes**")

            client.account_edit_state[user_id] = None

            from handlers.accounts_handlers import get_account
            account = get_account(user_id, account_id)
            if account:
                from handlers.keyboards import account_settings_keyboard
                await message.reply(
                    "**👤 Account Settings**",
                    reply_markup=account_settings_keyboard(account)
                )
        except ValueError:
            await message.reply("❌ Please send a valid number.")
        except Exception as e:
            await message.reply(f"❌ Error: `{e}`")
        return

    # ============================================================
    # 6. SETTINGS VALUES (target settings)
    # ============================================================
    state = getattr(client, "settings_state", {}).get(user_id)
    if state:
        action = state.get("action")
        chat_id = state.get("chat_id")

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
        return

# ============================================================
# 7. JOB CREATE – Source Detection (link or forward)
# ============================================================
    job_state = getattr(client, "job_create_state", {}).get(user_id)
    if job_state and job_state.get("step") == "source":
        from pyrogram.enums import ChatType
        from database import get_user_targets
        from handlers.keyboards import select_targets_keyboard

        source_chat_id = None
        last_msg_id = None

        if message.forward_from_chat:
            chat = message.forward_from_chat
            source_chat_id = chat.username or chat.id
            last_msg_id = message.forward_from_message_id
        else:
            m = re.search(
                r"(https?://)?(t\.me|telegram\.me|telegram\.dog)/(c/)?([a-zA-Z0-9_]+|\d+)/(\d+)",
                text
            )
            if not m:
                return await message.reply(
                    "❌ Couldn't read a source from that.\n\n"
                    "Forward a message from the source, or send a link like:\n"
                    "`https://t.me/c/1234567890/100`"
                )
            chat_part, last_msg_id = m.group(4), int(m.group(5))
            source_chat_id = int(f"-100{chat_part}") if chat_part.isdigit() else chat_part

        try:
            source_chat = await client.get_chat(source_chat_id)
        except Exception as e:
            return await message.reply(f"❌ Cannot access source chat.\nError: `{e}`")

        if source_chat.type not in [ChatType.CHANNEL, ChatType.GROUP, ChatType.SUPERGROUP]:
            return await message.reply("❌ Source must be a Channel or Group.")

        targets = get_user_targets(user_id)
        if not targets:
            client.job_create_state[user_id] = None
            return await message.reply("❌ No targets yet. Add one first (🎯 Targets → Add Target).")

        job_state.update({
            "source_chat_id": source_chat.id,
            "source_title": source_chat.title or "Unknown",
            "step": "targets",
            "selected_targets": [],
        })

        await message.reply(
            f"**📥 Source Detected:** {source_chat.title}\n\n"
            f"**📋 Create Job – Step 2**\n\nSelect target(s):",
            reply_markup=select_targets_keyboard(targets, [])
        )
        return

    # ============================================================
    # 8. JOB CREATE – Source Detection (link or forward)
    # ============================================================
    if job_state and job_state.get("step") == "source":
        # This part is better handled in source_handler, but we keep a simple version
        await message.reply(
            "Please use the job creation flow properly or forward a message / send a link."
        )
        return
