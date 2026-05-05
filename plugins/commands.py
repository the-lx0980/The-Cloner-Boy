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
    text = f"""
👋 Hello {m.from_user.first_name}!
I can forward messages, documents, videos, and media from a source channel/group to your target channel with advanced caption customization features.

**Basic Commands**

/set_channel - Set target channel where files will be forwarded.
/set_delay - Set delay between each forwarded message in second.
/set_skip - Skip messages from the beginning.
    Example: <code>/set_skip 100</code>
<code>cancel<code> - ⬅️ Stop current forwarding process.
/settings - Show current bot settings.
/reset_settings - Reset all saved settings.
/parse_caption - on/off This converts messy file names into clean professional captions.
/customised_caption on/off custom caption system.
/add_caption - Add your custom caption text.
/caption_position start/end/end_line
   start - Add custom caption before old caption.
   end -:Add custom caption directly at end.
   end_line - Add custom caption at end with blank line.
/all_type_link_remove on/off
    Remove: 
      http links, 
      https links
      t.me links
      telegram usernames
/replace old | new (Replace text inside captions.)
/reset_replace - Remove replace settings.
/forward_tag - on/off Forward original Telegram message with forward tag.
/id - Get your user ID and chat ID.
/stop - Restart the bot.

⚠️ Important 
• When Forward Tag is ON: Parse Caption, Link Remover, Replace Text, Custom Caption will not work because Telegram forwards the original message directly.
• All settings are temporary.
• If the bot restarts, settings will be lost.
• Send a Telegram post link or forward a message to start forwarding.

Example:
<code>https://t.me/channel/123</code>
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
