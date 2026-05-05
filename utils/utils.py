import logging
import asyncio
import re

from pyrogram.errors import FloodWait
from .parse_caption import extract_caption

logger = logging.getLogger("AIYearFetcher")


def remove_links(text):

    if not text:
        return text

    patterns = [
        r"https?://\S+",
        r"http?://\S+",
        r"www\.\S+",
        r"t\.me/\S+",
        r"telegram\.me/\S+",
        r"@\w+"
    ]

    for pattern in patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    # extra spaces remove
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" +", " ", text)

    return text.strip()


async def forwards_messages(
    bot,
    message,
    from_chat,
    to_chat,
    ai_caption=False,
    remove_link=False,
    custom_caption_enabled=False,
    custom_caption_text="",
    caption_position="end_line",
    forward_tag=False,
    replace_data=None
):

    try:

        if forward_tag:
            await bot.forward_messages(
                chat_id=to_chat,
                from_chat_id=from_chat,
                message_ids=message.id
            )
            return

        if message.media:
            media_type = message.media.value
            media = getattr(message, media_type, None)

            # unsupported media fallback
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
                or ""
            )

            if ai_caption and caption:
                try:
                    caption = await extract_caption(caption)
                except Exception as e:
                    logger.error(f"[AI Caption Error] {e}")

            
            if remove_link and caption:
                caption = remove_links(caption)

            
            if replace_data and caption:
                old_text = replace_data.get("old")
                new_text = replace_data.get("new")

                if old_text:
                    caption = caption.replace(old_text, new_text)

            
            if custom_caption_enabled and custom_caption_text:
                if caption_position == "start":
                    caption = (
                        f"{custom_caption_text}\n\n"
                        f"{caption}"
                    )

                elif caption_position == "end":
                    caption = (
                        f"{caption}"
                        f"{custom_caption_text}"
                    )

                else:
                    caption = (
                        f"{caption}\n\n"
                        f"{custom_caption_text}"
                    )

            await bot.send_cached_media(
                chat_id=to_chat,
                file_id=media.file_id,
                caption=caption if caption else None
            )

        else:

            text = message.text or message.caption or ""

            # AI Caption
            if ai_caption and text:

                try:
                    text = await extract_caption(text)

                except Exception as e:
                    logger.error(f"[AI Text Error] {e}")

            # Remove Links
            if remove_link and text:

                text = remove_links(text)

            # Replace Text
            if replace_data and text:

                old_text = replace_data.get("old")
                new_text = replace_data.get("new")

                if old_text:

                    text = text.replace(old_text, new_text)

            # Custom Caption
            if custom_caption_enabled and custom_caption_text:

                if caption_position == "start":

                    text = (
                        f"{custom_caption_text}\n\n"
                        f"{text}"
                    )

                elif caption_position == "end":

                    text = (
                        f"{text}"
                        f"{custom_caption_text}"
                    )

                else:

                    text = (
                        f"{text}\n\n"
                        f"{custom_caption_text}"
                    )

            # send text
            if text:

                await bot.send_message(
                    chat_id=to_chat,
                    text=text
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
        logger.error(f"[Forward Error] {e}")

        try:
            await bot.copy_message(
                chat_id=to_chat,
                from_chat_id=from_chat,
                message_id=message.id
            )

        except Exception as e2:
            logger.error(f"[Copy Retry Failed] {e2}")
