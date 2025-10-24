from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from config import Config as a
import asyncio
import sys
import os


@Client.on_message(filters.private & (filters.command("start") | filters.regex("start")) & filters.incoming)
async def start(_, m):
    if a.ADMINS and not ((str(m.from_user.id) in a.ADMINS) or (m.from_user.username in a.ADMINS)):
        return 
    text = """I can forward document and video (mp4 and mkv) files.

Forward your source channel message to this bot. If source channel is forward restricted last message link send to this bot.

/set_skip - Set skip message.
/set_channel - Set target channel.

Note - This bot not have a database, Then your details not saving permanently. If bot restarted your forward is stopping and your details is deleting."""
    await m.reply(f"👋 Hello {m.from_user.mention},\n\n{text}")

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
