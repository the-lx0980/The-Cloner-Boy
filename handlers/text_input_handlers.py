# handlers/text_input_handlers.py
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ChatType, ParseMode
import logging
import re

from database import (
    is_admin, update_target_settings, get_target, get_user_targets,
    add_target, add_forward_bot, add_forward_account, update_account,
    create_job, get_user_accounts, get_user_bots
)
from handlers.keyboards import (
    target_settings_keyboard, targets_list_keyboard,
    accounts_list_keyboard, bots_list_keyboard, jobs_list_keyboard
)

logger = logging.getLogger(__name__)


@Client.on_message(filters.private & filters.text & \~filters.command(["start", "targets", "cancel"]))
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
                state[user_id] = None
        await message.reply("✅ Cancelled.")
        return

    # ============================================================
    # 2. ADD TARGET
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
    # 3. ADD FORWARD BOT
    # ============================================================
    bot_add_state = getattr(client, "bot_add_state", {}).get(user_id)
    if bot_add_state:
        token = text.strip()
        if ":" not in token or len(token) < 30:
            return await message.reply("❌ Invalid bot token format.")

        try:
            # Optional: validate token by creating a temporary client (advanced)
            result = add_forward_bot(
                user_id=user_id,
                bot_token=token,
                bot_username=None,
                name=f"Bot {token[:8]}"
            )
            client.bot_add_state[user_id] = False

            if result is None:
                return await message.reply("⚠️ This bot token is already added.")

            await message.reply(
                f"✅ **Forward Bot Added!**\n\n"
                f"**Name:** {result.get('name')}\n"
                f"**Bot ID:** `{result.get('bot_id')}`"
            )

            bots = get_user_bots(user_id)
            await message.reply(
                f"**🤖 Forward Bots** ({len(bots)})",
                reply_markup=bots_list_keyboard(bots)
            )
        except Exception as e:
            await message.reply(f"❌ Error adding bot: `{e}`")
        return

    # ============================================================
    # 4. ACCOUNT EDIT (limit / sleep)
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
    # 5. SETTINGS VALUES (target settings)
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
    # 6. JOB CREATE – Final Options (last_msg_id + skip)
    # ============================================================
    job_state = getattr(client, "job_create_state", {}).get(user_id)
    if job_state and job_state.get("step") == "final_options":
        try:
            parts = text.split()
            last_msg_id = int(parts[0])
            skip = int(parts[1]) if len(parts) > 1 else 0

            if last_msg_id < 0 or skip < 0:
                return await message.reply("❌ Values cannot be negative.")

            # Create the job
            job = create_job(
                user_id=user_id,
                source_chat_id=job_state.get("source_chat_id"),
                source_title=job_state.get("source_title", "Unknown"),
                target_chat_ids=job_state.get("selected_targets", []),
                method=job_state.get("method"),
                account_ids=job_state.get("selected_accounts"),
                bot_id=job_state.get("bot_id"),
                last_msg_id=last_msg_id,
                skip=skip,
                future_new_posts=False,  # can be toggled later
                name=f"Job {job_state.get('source_title', '')[:20]}"
            )

            client.job_create_state[user_id] = None

            await message.reply(
                f"✅ **Job Created Successfully!**\n\n"
                f"**Job ID:** `{job['job_id']}`\n"
                f"**Source:** {job.get('source_title')}\n"
                f"**Targets:** {len(job.get('target_chat_ids', []))}\n"
                f"**Method:** `{job.get('method')}`\n\n"
                f"Go to **Jobs** section to start it."
            )

            from handlers.jobs_handlers import show_jobs_list
            # We can't easily call show_jobs_list here without a query, so just list
            jobs = get_user_jobs(user_id) if 'get_user_jobs' in globals() else []
            # fallback simple reply
        except ValueError:
            await message.reply("❌ Please send numbers only.\nExample: `15000` or `15000 200`")
        except Exception as e:
            await message.reply(f"❌ Error creating job: `{e}`")
        return

    # ============================================================
    # 7. JOB CREATE – Source Detection (link or forward)
    # ============================================================
    if job_state and job_state.get("step") == "source":
        # This part is better handled in source_handler, but we keep a simple version
        await message.reply(
            "Please use the job creation flow properly or forward a message / send a link."
        )
        return