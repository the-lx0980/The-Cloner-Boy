import asyncio
import re 
import logging
from pyrogram.enums import MessageMediaType, MessagesFilter
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait
from config import Config
logger = logging.getLogger(__name__)

CURRENT = {}
CHANNEL = {}
CANCEL = {}
FORWARDING = {}

@Client.on_message(filters.regex('cancel'))
async def cancel_forward(bot, message):
    cancel = await message.reply("Trying to cancel forwarding...")
    if FORWARDING.get(message.from_user.id):
        CANCEL[message.from_user.id] = True
        await cancel.edit("Successfully Forward Canceled!")
    else:
        await cancel.edit("No Forward Countinue Currently!")

@Client.on_message((filters.forwarded | (filters.regex("(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")) & filters.text) & filters.private & filters.incoming)
async def send_for_forward(bot, message):
    if message.text:
        regex = re.compile("(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")
        match = regex.match(message.text)
        if not match:
            return await message.reply('Invalid link for forward!')
        chat_id = match.group(4)
        last_msg_id = int(match.group(5))
        if chat_id.isnumeric():
            chat_id  = int(("-100" + chat_id))
    elif message.forward_from_chat.type in [enums.ChatType.CHANNEL, enums.ChatType.GROUP]:
        last_msg_id = message.forward_from_message_id
        chat_id = message.forward_from_chat.username or message.forward_from_chat.id
    else:
        return

    try:
        source_chat = await bot.get_chat(chat_id)
    except Exception as e:
        return await message.reply(f'Error - {e}')

    if source_chat.type not in [enums.ChatType.CHANNEL, enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        return await message.reply("I can forward only channels and groups.")

    target_chat_id = CHANNEL.get(message.from_user.id)
    if not target_chat_id:
        return await message.reply("You not added target channel.\nAdd using /set_channel command.")

    try:
        target_chat = await bot.get_chat(target_chat_id)
    except Exception as e:
        return await message.reply(f'Error - {e}')
    # last_msg_id is same to total messages
    approval = await message.chat.ask(
        text = f'''Do You Want Forward? If You Want Forward Send Me "<code>yes</code>" Else Send Me "<code>no</code>"'''
    )
    approval = approval.text.lower()  
    if approval.strip() == "yes":
        if FORWARDING.get(message.from_user.id):
            return await message.reply('Wait until previous process complete.')
        msg = await message.reply('Starting Forwarding...')
        try:
            chat = int(chat_id)
        except:
            chat = chat_id
        lst_msg_id = last_msg_id
        chat_id_mod = False
        await forward_files(int(lst_msg_id), chat, msg, bot, message.from_user.id, chat_id_mod)
    else:
        if approval.strip() == "no":
            return await message.reply("Okay")
        else:
            return await message.reply("Invalid reply, Try Again!")
            
                    
@Client.on_message(filters.private & filters.command(['set_skip']))
async def set_skip_number(bot, message):
    try:
        _, skip = message.text.split(" ")
    except:
        return await message.reply("Give me a skip number.")
    try:
        skip = int(skip)
    except:
        return await message.reply("Only support in numbers.")
    CURRENT[message.from_user.id] = int(skip)
    await message.reply(f"Successfully set <code>{skip}</code> skip number.")


@Client.on_message(filters.private & filters.command(['set_channel']))
async def set_target_channel(bot, message):    
    if Config.ADMINS and not ((str(message.from_user.id) in Config.ADMINS) or (message.from_user.username in Config.ADMINS)):
        return await message.reply("You Are Not Allowed To Use This UserBot")
    try:
        _, chat_id = message.text.split(" ")
    except:
        return await message.reply("Give me a target channel ID")
    try:
        chat_id = int(chat_id)
    except:
        return await message.reply("Give me a valid ID")

    try:
        chat = await bot.get_chat(chat_id)
    except:
        return await message.reply("Make me a admin in your target channel.")
    CHANNEL[message.from_user.id] = int(chat.id)
    await message.reply(f"Successfully set {chat.title} target channel.")
    
@Client.on_message(filters.chat(-1003194225143))
async def auto_get_link(bot, message):
    chat_id_regex = re.compile(r"-100\d{7,}")
    matches = re.findall(chat_id_regex, message.text)
    if not matches:
        return 
    link = None
    for chat_id_str in matches:
        chat_id = int(chat_id_str)
        try:
            # check bot is member or not
            chat = await bot.get_chat(chat_id)
            async for msg in bot.get_chat_history(chat_id, limit=1):
                if msg.chat.username:
                    link = f"https://t.me/{msg.chat.username}/{msg.id}"
                else:
                    link = f"https://t.me/c/{str(msg.chat.id)[4:]}/{msg.id}"
                break

        except Exception as e:
            await message.reply_text(f"⚠️ Chat ID `{chat_id}` skip kiya: `{e}`")
    try:
        if link:
            regex = re.compile("(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")
            match = regex.match(link)
            if not match:
                return await message.reply('Invalid link for forward!')
            
            last_msg_id = int(match.group(5))
            chat_id = chat.id
            msg = await message.reply('Forwarding Started...')
            chat_id_mod = True
            user_id = message.from_user.id
            await forward_files(last_msg_id, chat_id, msg, bot, user_id, chat_id_mod)
        else:
            await message.reply('No Link Found')
    except Exception as e:
        return await message.reply(f"Error: {e}")        
        
async def forward_files(lst_msg_id, chat, msg, bot, user_id, chat_id_mod):
    if chat_id_mod:
        status_chat = -1001631481154
        status_msg_id = 15
        try:
            msg_text = await bot.get_messages(status_chat, status_msg_id)
        except Exception as e:
            logger.exception(e)
            return await msg.edit(f"Error - {e}")
        msg_text = msg_text.text   
        target = re.search(r"Target chat\s*:\s*(-?\d+)", msg_text, re.IGNORECASE)
        skip = re.search(r"Skip Msg\s*:\s*(\d+)", msg_text, re.IGNORECASE)
        duplicate = re.search(r"Get Duplicate\s*:\s*(\w+)", msg_text, re.IGNORECASE)

        target_chat = target.group(1) if target else None
        skip_msg = skip.group(1) if skip else None
        get_duplicate = duplicate.group(1).lower() if duplicate else "off"
        duplicate_search_id = None
        if get_duplicate == "on":
            dup_search = re.search(r"Duplicate Search ID\s*:\s*(-?\d+)", msg_text, re.IGNORECASE)
            if dup_search:
                duplicate_search_id = dup_search.group(1)
                
        try:
            current = int(skip_msg)
            target_chat = int(target_chat)
            if duplicate_search_id:
                duplicate_search_id = int(duplicate_search_id) 
        except Exception as e:
            return await msg.edit(f"Error: {e}")
    else:
        target_chat = CHANNEL.get(user_id)
        current = CURRENT.get(user_id) if CURRENT.get(user_id) else 0
        duplicate_search_id = None
    
    if not target_chat:
        return await msg.edit(f"First Set Target Chat")
          
    # Status    
    forwarded = 0
    deleted = 0
    unsupported = 0
    fetched = 0
    duplicate = 0
    CANCEL[user_id] = False
    FORWARDING[user_id] = True        
    # lst_msg_id is same to total messages

    try:
        async for message in bot.iter_messages(chat, lst_msg_id, current):
            if CANCEL.get(user_id):
                await msg.edit(f"Successfully Forward Canceled!")
                FORWARDING[user_id] = False 
                break
            if forwarded == 500:
                await msg.edit(f"Forward stopped! You Reached Max Limit\n<b>Message ID</b>: <code>{message.id}</code>\n<b>Forwarded</b>: <code>{forwarded}</code>\nDuplicate: <code>{duplicate}</code>")
                FORWARDING[user_id] = False 
                break
            current += 1
            fetched += 1
            if current % 20 == 0:
                await msg.edit_text(text=f'''Forward Processing...\n\nTotal Messages: <code>{lst_msg_id}</code>\nCompleted Messages: <code>{current} / {lst_msg_id}</code>\nForwarded Files: <code>{forwarded}</code>\nDeleted Messages Skipped: <code>{deleted}</code>\nNon Media Files: <code>{unsupported}</code>\nDuplicate: <code>{duplicate}</code>\n\n send "<code>cancel</code>" for stop''')
            if message.empty:
                deleted += 1
                continue
            if not message.media:
                continue
            if message.media not in [MessageMediaType.DOCUMENT, MessageMediaType.VIDEO]:
                unsupported += 1
                continue
            
            if duplicate_search_id:
                if message.media == MessageMediaType.VIDEO:
                    media_type = MessagesFilter.VIDEO
                    file_n = 'video'
                else:
                    media_type = MessagesFilter.DOCUMENT  
                    file_n = 'document'
                if message.caption:
                    search_text = message.caption
                else:
                    search_text = message.video.file_name if message.video.file_name else message.document.file_name
                file_name = False    
                async for msg_s in bot.search_messages(int(duplicate_search_id),query=search_text,filter=media_type):       
                    if msg_s.caption:
                        file_name = True
                    elif file_n == 'video':
                        file_name = msg_s.video.file_name
                    else:
                        file_name = msg_s.document.file_name    
                if file_name:
                    duplicate += 1
                    continue             
            try:         
                media = getattr(message, message.media.value, None)
                if media:
                    try:
                        await bot.send_cached_media(
                            chat_id=target_chat,
                            file_id=media.file_id,
                            caption=message.caption
                        )
                    except FloodWait as e:
                        await asyncio.sleep(e.value)  # Wait "value" seconds before continuing
                        await bot.send_cached_media(
                                chat_id=target_chat,
                                file_id=media.file_id,
                                caption=message.caption
                        )
            except Exception as e:
                logger.exception(e)
                return await msg.reply(f"Forward Canceled!\n\nError - {e}")               
            forwarded += 1
            await asyncio.sleep(4)            
    except Exception as e:
        logger.exception(e)
        await msg.reply(f"Forward Canceled!\n\nError - {e}")
        if chat_id_mod:
            text = f"Target chat: {target_chat}\nSkip Msg: {current}\nGet Duplicate: {get_duplicate}\nDuplicate Search ID: {duplicate_search_id or ''}"
            await bot.edit_message_text(status_chat, status_msg_id, text)
        FORWARDING[user_id] = False
    else:
        await msg.edit(f'Forward Completed!\n\nTotal Messages: <code>{lst_msg_id}</code>\nCompleted Messages: <code>{current} / {lst_msg_id}</code>\nFetched Messages: <code>{fetched}</code>\nTotal Forwarded Files: <code>{forwarded}</code>\nDeleted Messages Skipped: <code>{deleted}</code>\nNon Media Files: <code>{unsupported}</code>\nDuplicate: <code>{duplicate}</code>')
        FORWARDING[user_id] = False
