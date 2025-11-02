# Lx 0980

async def get_latest_media_link(bot, chat_id: int):
    offset_id = 0
    batch_size = 100 
    while True:
        found_any = False
        async for msg in bot.get_chat_history(chat_id, offset_id=offset_id, limit=batch_size):
            found_any = True
            offset_id = msg.id

            if msg.video or msg.document:
                if msg.chat.username:
                    return f"https://t.me/{msg.chat.username}/{msg.id}"
                else:
                    return f"https://t.me/c/{str(msg.chat.id)[4:]}/{msg.id}"
        if not found_any:
            break
    return None
