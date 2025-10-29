import logging            
import asyncio
from pyrogram.errors import FloodWait
from pyrogram import enums
from .parse_caption import extract_caption

logger = logging.getLogger("AIYearFetcher")

async def forwards_messages(bot, message, from_chat, to_chat, ai_caption):
    try:
        if message.media:
            media_type = message.media.value
            media = getattr(message, media_type, None)

            if not hasattr(media, "file_id"):
                await bot.copy_message(
                    chat_id=to_chat,
                    from_chat_id=from_chat,
                    message_id=message.id
                )
                return

            caption = (
                message.caption
                or getattr(message.video, "file_name", None)
                or getattr(message.document, "file_name", None)
                or getattr(message.audio, "file_name", None)
            )

            if ai_caption and caption:
                try:
                    caption = await extract_caption(caption)
                except Exception as e:
                    logger.error(f"[AI Caption Error] {e}")

            await bot.send_cached_media(
                chat_id=to_chat,
                file_id=media.file_id,
                caption=f"**{caption or ''}**" if caption else None,
                parse_mode=enums.ParseMode.MARKDOWN
            )

        else:
            await bot.copy_message(
                chat_id=to_chat,
                from_chat_id=from_chat,
                message_id=message.id
            )

    except FloodWait as e:
        await asyncio.sleep(e.value)
        await forwards_messages(bot, message, from_chat, to_chat, ai_caption)

    except Exception as e:
        logger.info(f"[Forward Error Ignored] {e}")
        try:
            await bot.copy_message(
                chat_id=to_chat,
                from_chat_id=from_chat,
                message_id=message.id
            )
        except Exception as e2:
            logger.error(f"[Copy Retry Failed] {e2}")
