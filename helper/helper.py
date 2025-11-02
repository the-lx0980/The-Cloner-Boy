import logging

logger = logging.getLogger(__name__)

async def get_latest_media_link(bot, chat_id: int, message):
    offset_id = 0
    batch_size = 100

    logger.info(f"🔍 Searching for latest media in chat_id: {chat_id}")

    while True:
        found_any = False
        try:
            async for msg in bot.get_chat_history(chat_id, offset_id=offset_id, limit=batch_size):
                found_any = True
                offset_id = msg.id
                logger.info(offset_id) 

                # Check if message has media (video/document)
                if msg.video or msg.document:
                    if msg.chat.username:
                        link = f"https://t.me/{msg.chat.username}/{msg.id}"
                    else:
                        link = f"https://t.me/c/{str(msg.chat.id)[4:]}/{msg.id}"

                    logger.info(f"✅ Found latest media in {chat_id}: {link}")

                    await message.reply(f"✅ Latest media link found:\n\n{link}")

                    return link

            if not found_any:
                break

        except Exception as e:
            logger.exception(f"❌ Error while fetching media from chat_id {chat_id}: {e}")
            break

    # No media found
    logger.warning(f"⚠️ No video/document found in chat_id: {chat_id}")
    if reply_message:
        await message.reply(f"⚠️ No video/document found in `{chat_id}`.")
    return None
