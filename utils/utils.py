import logging
import asyncio
import re

from pyrogram.errors import FloodWait
from pyrogram import enums
from .parse_caption import extract_caption

logger = logging.getLogger("AIYearFetcher")


def remove_links(text):
    if not text:
        return text

    patterns = [
        r"https?://\\S+",
        r"t\\.me/\\S+",
        r"@\\w+"
    ]

    for pattern in patterns:
        text = re.sub(pattern, "", text)

    return text.strip()


async def forwards_messages(
    bot,
    message,
    from_chat,
    to_chat,
    ai_caption,
    remove_link=False,
    custom_caption_enabled=False,
    custom_caption_text="",
    caption_position="end_line",
    forward_tag=False,
    replace_data=None
):

    try:
        if message.media:

            media_type = message.media.value
            media = getattr(message, media_type, None)

            if not hasattr(media, "file_id"):

                if forward_tag:
                    await bot.forward_messages(
                        chat_id=to_chat,
                        from_chat_id=from_chat,
                        message_ids=message.id
                    )
                else:
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

            # AI Caption
            if ai_caption and caption:
                try:
                    caption = await extract_caption(caption)
                except Exception as e:
                    logger.error(f"[AI Caption Error] {e}")

            # Remove Links
            if remove_link and caption:
                caption = remove_links(caption)

            # Replace Text
            if replace_data and caption:

                old_text = replace_data.get("old")
                new_text = replace_data.get("new")

                if old_text:
                    caption = caption.replace(old_text, new_text)

            # Custom Caption
            if custom_caption_enabled and custom_caption_text:

                if caption_position == "start":
                    caption = f"{custom_caption_text}\n\n{caption or ''}"

                elif caption_position == "end":
                    caption = f"{caption or ''}{custom_caption_text}"

                else:
                    caption = f"{caption or ''}\n\n{custom_caption_text}"

            await bot.send_cached_media(
                chat_id=to_chat,
                file_id=media.file_id,
                caption=f"**{caption or ''}**" if caption else None,
                parse_mode=enums.ParseMode.MARKDOWN
            )

        else:

            if forward_tag:
                await bot.forward_messages(
                    chat_id=to_chat,
                    from_chat_id=from_chat,
                    message_ids=message.id
                )
            else:
                await bot.copy_message(
                    chat_id=to_chat,
                    from_chat_id=from_chat,
                    message_id=message.id
                )

    except FloodWait as e:

        await asyncio.sleep(e.value)

        await forwards_messages(
            bot,
            message,
            from_chat,
            to_chat,
            ai_caption,
            remove_link,
            custom_caption_enabled,
            custom_caption_text,
            caption_position,
            forward_tag,
            replace_data
        )

    except Exception as e:

        logger.info(f"[Forward Error Ignored] {e}")

        try:

            if forward_tag:
                await bot.forward_messages(
                    chat_id=to_chat,
                    from_chat_id=from_chat,
                    message_ids=message.id
                )
            else:
                await bot.copy_message(
                    chat_id=to_chat,
                    from_chat_id=from_chat,
                    message_id=message.id
                )

        except Exception as e2:
            logger.error(f"[Copy Retry Failed] {e2}")
