# handlers/bots_handlers.py
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery

from database import (
    is_admin, ensure_user, get_user_bots, get_bot,
    add_forward_bot, update_bot, delete_bot
)
from handlers.keyboards import (
    bots_list_keyboard, bot_settings_keyboard,
    confirm_delete_bot_keyboard
)
import logging

logger = logging.getLogger(__name__)


async def show_bots_list(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    bots = get_user_bots(user_id)

    if not bots:
        text = (
            "**🤖 Forward Bots**\n\n"
            "You have no forwarding bots yet.\n"
            "Click **Add Bot** to add a bot token."
        )
    else:
        text = f"**🤖 Forward Bots** ({len(bots)})\n\nSelect a bot to manage:"

    await query.message.edit_text(text, reply_markup=bots_list_keyboard(bots))
    await query.answer()


@Client.on_callback_query(filters.regex(r"^bot:"))
async def bots_callbacks(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    if not is_admin(user_id):
        return await query.answer("Not allowed", show_alert=True)

    data = query.data
    ensure_user(user_id)

    if data == "bot:list":
        await show_bots_list(client, query)
        return

    if data == "bot:add":
        await query.message.edit_text(
            "**➕ Add Forwarding Bot**\n\n"
            "Send the **Bot Token** you got from @BotFather.\n\n"
            "Example:\n`123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`\n\n"
            "Type /cancel to cancel."
        )
        client.bot_add_state = getattr(client, "bot_add_state", {})
        client.bot_add_state[user_id] = True
        return await query.answer()

    if data.startswith("bot:open:"):
        bot_id = data.split(":")[2]
        bot = get_bot(user_id, bot_id)
        if not bot:
            return await query.answer("Bot not found", show_alert=True)

        name = bot.get("name") or bot.get("bot_username") or "Bot"
        status = bot.get("status", "active")
        total = bot.get("total_forwarded", 0)

        text = (
            f"**🤖 Bot Settings**\n\n"
            f"**Name:** {name}\n"
            f"**Username:** @{bot.get('bot_username') or 'N/A'}\n"
            f"**Status:** `{status}`\n"
            f"**Total Forwarded:** `{total}`\n"
        )
        await query.message.edit_text(text, reply_markup=bot_settings_keyboard(bot))
        return await query.answer()

    if data.startswith("bot:toggle_status:"):
        bot_id = data.split(":")[2]
        bot = get_bot(user_id, bot_id)
        if not bot:
            return await query.answer("Bot not found", show_alert=True)

        current = bot.get("status", "active")
        new_status = "disabled" if current == "active" else "active"
        update_bot(user_id, bot_id, {"status": new_status})

        bot = get_bot(user_id, bot_id)
        await query.message.edit_text(
            f"**🤖 Bot Settings**\n\nStatus updated to `{new_status}`",
            reply_markup=bot_settings_keyboard(bot)
        )
        return await query.answer(f"Status → {new_status}")

    if data.startswith("bot:delete:"):
        bot_id = data.split(":")[2]
        bot = get_bot(user_id, bot_id)
        if not bot:
            return await query.answer("Bot not found", show_alert=True)

        await query.message.edit_text(
            f"**⚠️ Delete Bot?**\n\n"
            f"**{bot.get('name')}**\n\n"
            f"This action cannot be undone.",
            reply_markup=confirm_delete_bot_keyboard(bot_id)
        )
        return await query.answer()

    if data.startswith("bot:confirm_delete:"):
        bot_id = data.split(":")[2]
        success = delete_bot(user_id, bot_id)
        if success:
            await query.answer("✅ Bot deleted", show_alert=True)
            await show_bots_list(client, query)
        else:
            await query.answer("Failed to delete", show_alert=True)
        return