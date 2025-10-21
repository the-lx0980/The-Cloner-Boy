import asyncio
from pyrogram.errors import FloodWait
from pyrogram import enums
from .tmdb_utils import extract_caption_parser

async def forwards_messages(bot, message, from_chat, to_chat, ai_caption):
    if message.media: 
        media_type = message.media.value
        media = getattr(message, media_type, None)
        if media:
            if message.caption:
                caption = message.caption
            elif message.video:
                caption = message.video.file_name
            elif message.document:
                caption = message.document.file_name
            elif message.audio:
                caption = message.audio.file_name 
            else:
                caption = None

            if ai_caption and caption:
                caption = await extract_caption_parser(caption)

            try:
                await bot.send_cached_media(
                    chat_id=to_chat,
                    file_id=media.file_id,
                    caption=f"**{caption or ''}**"
                )
            except FloodWait as e:
                await asyncio.sleep(e.value)
                await forwards_messages(bot, message, from_chat, to_chat, ai_caption)
    else:
        try:
            await bot.copy_message(
                chat_id=to_chat,
                from_chat_id=from_chat,
                message_id=message.id,
                caption=f'**{message.caption or ""}**',
                parse_mode=enums.ParseMode.MARKDOWN
            )
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await forwards_messages(bot, message, from_chat, to_chat, ai_caption)
