from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from config import Config as a
import asyncio
import sys
import os
import logging
from utils.database import collection  # Assuming collection is exported from database.py

logger = logging.getLogger("ClearDBCommand")


@Client.on_message(filters.private & (filters.command("start") | filters.regex("start")) & filters.incoming)
async def start(_, m):
    if a.ADMINS and not ((str(m.from_user.id) in a.ADMINS) or (m.from_user.username in a.ADMINS)):
        return 
    text = f"""
👋 Hello {m.from_user.first_name}!

I can forward **documents** and **videos** (mp4/mkv) from a source channel to your target channel.

**Commands:**
/set_skip <number> - Skip first messages.
/set_channel <channel_id> - Set target channel.
/set_delay <seconds> - Set delay between forwards.
/parse_caption on/off - Enable/disable parse caption formatting.
/stop - restart the bot.
/id - get users id and chat id. 

⚠️ Note: Your settings are temporary. If the bot restarts, forwarding stops and settings are lost.
"""
    await m.reply(text)
    
@Client.on_message(filters.command("stop"))
async def stop_button(bot, m):
    if a.ADMINS and not ((str(m.from_user.id) in a.ADMINS) or (m.from_user.username in a.ADMINS)):
        return
    msg = await bot.send_message(
        text="Stoping all processes...",
        chat_id=m.chat.id
    )
    await asyncio.sleep(1)
    await msg.edit("All Processes Stopped and Restarted")
    os.execl(sys.executable, sys.executable, *sys.argv)

@Client.on_message(filters.command('id'))
async def showid(client, message):
    chat_type = message.chat.type
    if chat_type == enums.ChatType.PRIVATE:
        user_id = message.chat.id
        first = message.from_user.first_name
        last = message.from_user.last_name or "None"
        username = f"@{message.from_user.username}" or "None"
        await message.reply_text(
            f"★ First Name: {first}\n★ Last Name: {last}\n★ Username: {username}\n★ User ID: <code>{user_id}</code>",
            quote=True
        )

    elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        _id = ""
        _id += (
            "★ Chat ID: "
            f"<code>{message.chat.id}</code>\n"
        )
        if message.reply_to_message:
            _id += (
                "★ User ID: "
                f"<code>{message.from_user.id if message.from_user else 'Anonymous'}</code>\n"
                "★ Replied User ID: "
                f"<code>{message.reply_to_message.from_user.id if message.reply_to_message.from_user else 'Anonymous'}</code>\n"
            )
            file_info = get_file_id(message.reply_to_message)
        else:
            _id += (
                "★ User ID: "
                f"<code>{message.from_user.id if message.from_user else 'Anonymous'}</code>\n"
            )
            file_info = get_file_id(message)
        if file_info:
            _id += (
                f"★ {file_info.message_type}: "
                f"<code>{file_info.file_id}</code>\n"
            )
        await message.reply_text(
            _id,
            quote=True
        )

    elif chat_type == enums.ChatType.CHANNEL:
        await message.reply_text(f'★ Channel ID: <code>{message.chat.id}</code>')


@Client.on_message(filters.command("cleardb") & filters.private)
async def cleardb_command(client: Client, message: Message):
    if collection is None:
        await message.reply_text("⚠️ MongoDB connection not available.")
        return

    total_docs = collection.count_documents({})
    if total_docs == 0:
        await message.reply_text("📦 Database is already empty.")
        return

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Confirm Delete", callback_data="confirm_delete"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_delete")
            ]
        ]
    )

    await message.reply_text(
        f"⚠️ This will delete **all {total_docs} documents** from the database!\n\n"
        "Do you want to continue?",
        reply_markup=keyboard,
        parse_mode=enums.ParseMode.MARKDOWN
    )


@Client.on_callback_query()
async def cleardb_callback(client: Client, callback_query):
    if collection is None:
        await callback_query.answer("⚠️ MongoDB not available.", show_alert=True)
        return

    if callback_query.data == "cancel_delete":
        await callback_query.message.edit_text("❌ Deletion canceled.")
        await callback_query.answer()
        return

    if callback_query.data == "confirm_delete":
        total_docs = collection.count_documents({})
        if total_docs == 0:
            await callback_query.message.edit_text("📦 Database is already empty.")
            await callback_query.answer()
            return

        result = collection.delete_many({})
        await callback_query.message.edit_text(
            f"✅ Database cleaned successfully!\nDeleted {result.deleted_count} documents."
        )
        await callback_query.answer()
