import asyncio
import os
import sys

from pyrogram import Client, filters, enums
from pyrogram.types import Message
from pyrogram.errors import (
    FloodWait,
    UserAlreadyParticipant,
    InviteRequestSent,
    InviteHashExpired
)

from config import Config as a


def is_admin(message: Message):
    if not a.ADMINS:
        return True
    uid = str(message.from_user.id)
    uname = message.from_user.username
    return uid in a.ADMINS or (uname and uname in a.ADMINS)


@Client.on_message(filters.private & filters.command("start"))
async def start(_, m: Message):
    if not is_admin(m):
        return

    text = (
        "I can forward document and video (mp4 and mkv) files.\n\n"
        "Forward your source channel message to this bot.\n\n"
        "/set_skip - Set skip message\n"
        "/set_channel - Set target channel\n"
        "/id - Get User ID or Chat ID\n"
        "/stop - Restart bot\n"
        "/join - Join any chat (invite / public)\n"
        "/leave - Leave chat (chat_id)\n\n"
        "⚠️ No database is used. Restart will reset everything."
    )

    await m.reply(f"👋 Hello {m.from_user.mention},\n\n{text}")


@Client.on_message(filters.command("stop") & filters.private)
async def stop_button(bot: Client, m: Message):
    if not is_admin(m):
        return

    msg = await m.reply("⏳ Stopping all processes...")
    await asyncio.sleep(1)
    await msg.edit("✅ Restarting now...")
    os.execl(sys.executable, sys.executable, *sys.argv)


@Client.on_message(filters.command("id"))
async def show_id(_, message: Message):

    chat_type = message.chat.type

    if chat_type == enums.ChatType.PRIVATE:
        user = message.from_user
        username = f"@{user.username}" if user.username else "None"

        await message.reply_text(
            f"★ First Name: {user.first_name}\n"
            f"★ Last Name: {user.last_name or 'None'}\n"
            f"★ Username: {username}\n"
            f"★ User ID: <code>{user.id}</code>",
            quote=True
        )

    elif chat_type in (enums.ChatType.GROUP, enums.ChatType.SUPERGROUP):
        text = f"★ Chat ID: <code>{message.chat.id}</code>\n"

        if message.reply_to_message and message.reply_to_message.from_user:
            text += (
                f"★ Your ID: <code>{message.from_user.id}</code>\n"
                f"★ Replied User ID: "
                f"<code>{message.reply_to_message.from_user.id}</code>\n"
            )
        else:
            text += f"★ Your ID: <code>{message.from_user.id}</code>\n"

        await message.reply_text(text, quote=True)

    elif chat_type == enums.ChatType.CHANNEL:
        await message.reply_text(
            f"★ Channel ID: <code>{message.chat.id}</code>"
        )


@Client.on_message(filters.command("join") & filters.private)
async def join_chat(client: Client, message: Message):
    if not is_admin(message):
        return

    if len(message.command) < 2:
        return await message.reply("❌ Usage:\n`/join <link | @username>`")

    raw = message.command[1].strip()

    if raw.startswith("https://t.me/"):
        part = raw.replace("https://t.me/", "")
    elif raw.startswith("t.me/"):
        part = raw.replace("t.me/", "")
    else:
        part = raw

    try:
        # INVITE LINK
        if part.startswith("+") or "joinchat" in raw:
            chat = await client.join_chat(raw)

        # PUBLIC USERNAME
        else:
            if not part.startswith("@"):
                part = f"@{part}"
            chat = await client.join_chat(part)

        title = chat.title or "Private Chat"

        await message.reply(
            f"✅ **Joined Successfully**\n\n"
            f"📌 **Chat:** `{title}`\n"
            f"🆔 **ID:** `{chat.id}`"
        )

    except InviteRequestSent:
        chat = await client.get_chat(part)
        await message.reply(
            f"⏳ **Join Request Sent**\n"
            f"📌 **Chat:** `{chat.title}`"
        )

    except UserAlreadyParticipant:
        chat = await client.get_chat(part)
        await message.reply(
            f"⚠️ **Already Joined**\n"
            f"📌 **Chat:** `{chat.title}`"
        )

    except InviteHashExpired:
        await message.reply("❌ Invite link expired / invalid")

    except FloodWait as e:
        await asyncio.sleep(e.value)

    except Exception as e:
        await message.reply(f"❌ **Error:** `{e}`")



@Client.on_message(filters.command("leave") & filters.private)
async def leave_chat(client: Client, message: Message):
    if not is_admin(message):
        return

    if len(message.command) < 2:
        return await message.reply("❌ Usage:\n`/leave <chat_id>`")

    try:
        chat_id = int(message.command[1])
        await client.leave_chat(chat_id)

        await message.reply(
            f"✅ **Left Chat Successfully**\n"
            f"🆔 **Chat ID:** `{chat_id}`"
        )

    except FloodWait as e:
        await asyncio.sleep(e.value)
        await message.reply("⏳ FloodWait, try again later")

    except Exception as e:
        await message.reply(f"❌ **Error:** `{e}`")
