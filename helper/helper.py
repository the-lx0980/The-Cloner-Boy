import logging
from pyrogram.enums import MessagesFilter

logger = logging.getLogger(__name__)

async def get_latest_media_link(bot, chat_id: int, message):
    """Find and return the latest video/document link in a chat."""
    try:
        logger.info(f"🔍 Searching latest media in chat {chat_id}")

        # Search messages (newest first)
        async for msg in bot.search_messages(
            chat_id,
            filter=MessagesFilter.EMPTY,  # fetch all types
            limit=100
        ):
            if msg.video or msg.document:
                # Build link manually (msg.link doesn't always exist)
                if msg.chat.username:
                    link = f"https://t.me/{msg.chat.username}/{msg.id}"
                else:
                    link = f"https://t.me/c/{str(msg.chat.id)[4:]}/{msg.id}"

                logger.info(f"✅ Found latest media in {chat_id}: {link}")
                await message.reply(f"✅ Latest media link found:\n\n{link}")
                return link

        # No media found
        logger.warning(f"⚠️ No video/document found in chat {chat_id}")
        await message.reply(f"⚠️ No video/document found in `{chat_id}`.")
        return None

    except Exception as e:
        logger.exception(f"❌ Error fetching media from chat {chat_id}: {e}")
        await message.reply(f"❌ Error while fetching media from `{chat_id}`:\n\n{e}")
        return None       
