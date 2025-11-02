import asyncio
import re 
import logging
from pyrogram.enums import MessageMediaType, MessagesFilter
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait, MessageNotModified
from config import Config
from helper.helper import get_latest_media_link

logger = logging.getLogger(__name__)

CURRENT = {}
CHANNEL = {}
CANCEL = {}
FORWARDING = {}
STATUS_CHAT = Config.STATUS_CHAT_GROUP_ID

@Client.on_message(filters.regex('cancel'))
async def cancel_forward(bot, message):
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        track_chat_id = message.chat.id
        if track_chat_id != STATUS_CHAT:
            return    
    else:
        track_chat_id = message.from_user.id
    cancel = await message.reply("Trying to cancel forwarding...")
    if FORWARDING.get(track_chat_id):
        CANCEL[track_chat_id] = True
        await cancel.edit("Successfully Forward Canceled!")
    else:
        await cancel.edit("No Forward Countinue Currently!")

@Client.on_message((filters.forwarded | (filters.regex("(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")) & filters.text) & filters.private & filters.incoming)
async def send_for_forward(bot, message):
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        track_chat_id = message.chat.id
        if track_chat_id != STATUS_CHAT:
            return
    else:
        track_chat_id = message.from_user.id       
            
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
        if FORWARDING.get(track_chat_id):
            return await message.reply('Wait until previous process complete.')
        msg = await message.reply('Starting Forwarding...')
        try:
            chat = int(chat_id)
        except:
            chat = chat_id
        lst_msg_id = last_msg_id
        chat_id_mod = False
        await forward_files(int(lst_msg_id), chat, msg, bot, track_chat_id, chat_id_mod)
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
    
@Client.on_message(filters.chat(STATUS_CHAT))
async def auto_get_link(bot, message):
    chat_id_regex = re.compile(r"-100\d{7,}")
    match = chat_id_regex.search(str(message.text))
    if not match:
        return 
    
    if FORWARDING.get(STATUS_CHAT):
        return await message.reply('Wait until previous process complete.')
        
    chat_ids = int(match.group(0))
    
    link = None
    try:
        try:
            chat = await bot.get_chat(chat_ids)
        except:
            return await message.reply(f"Make sure userbot is member of source chat {chat_id}.")
        link = await get_latest_media_link(bot, chat.id, message)
        if not link:
            return
    except Exception as e:
        return await message.reply_text(f"⚠️ Error `{e}`")
            
    try:
        if link:
            regex = re.compile("(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")
            match = regex.match(link)
            if not match:
                return await message.reply('Invalid link for forward!')
            
            last_msg_id = int(match.group(5))
            chat_id = chat_ids
            msg = await message.reply('Forwarding Started...')
            chat_id_mod = True
            track_chat_id = message.chat.id
            await forward_files(last_msg_id, chat_id, msg, bot, track_chat_id, chat_id_mod)
        else:
            await message.reply('No Link Found')
    except Exception as e:
        return await message.reply(f"Error: {e}")        
        
async def forward_files(lst_msg_id, from_chat, msg, bot, track_chat_id, chat_id_mod):
    if chat_id_mod:
        status_chat = Config.STATUS_CHANNEL_ID
        status_msg_id = Config.STATUS_CHANNEL_MSG_ID

        try:
            chat = await bot.get_chat(status_chat)
        except:
            return await msg.edit("Make sure userbot is admin in your status channel and status channel id is correct.")
            
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
        target_chat = CHANNEL.get(track_chat_id)
        current = CURRENT.get(track_chat_id) if CURRENT.get(track_chat_id) else 0
        duplicate_search_id = None
    
    if not target_chat:
        return await msg.edit(f"First Set Target Chat")
        
    try:
        chat = await bot.get_chat(target_chat)
    except:
        return await msg.edit("Make sure userbot is admin in your in target channel and target chat id is correct.")   
    
    if duplicate_search_id:
        try:
            chat = await bot.get_chat(duplicate_search_id)
        except:
            return await msg.edit("Make sure userbot is mmember of duplicate search channel and chat id is correct.")   
            
          
    # Status    
    forwarded = 0
    deleted = 0
    unsupported = 0
    fetched = 0
    duplicate = 0
    CANCEL[track_chat_id] = False
    FORWARDING[track_chat_id] = True        
    # lst_msg_id is same to total messages

    try:
        async for message in bot.iter_messages(from_chat, lst_msg_id, current):
            if CANCEL.get(track_chat_id):
                await msg.edit(f"Successfully Forward Canceled!")
                FORWARDING[track_chat_id] = False 
                break
            if forwarded == 500:
                await msg.edit(f"Forward stopped! You Reached Max Limit\n<b>Message ID</b>: <code>{message.id}</code>\n<b>Forwarded</b>: <code>{forwarded}</code>\nDuplicate: <code>{duplicate}</code>")
                FORWARDING[track_chat_id] = False 
                break
            current += 1
            fetched += 1
            if current % 20 == 0:
                await msg.edit_text(text=f'''Forward Processing...\n\nTotal Messages: <code>{lst_msg_id}</code>\nCompleted Messages: <code>{current} / {lst_msg_id}</code>\nForwarded Files: <code>{forwarded}</code>\nDeleted Messages Skipped: <code>{deleted}</code>\nNon Media Files: <code>{unsupported}</code>\nDuplicate: <code>{duplicate}</code>\n\n send "<code>cancel</code>" for stop''')
            if message.empty:
                deleted += 1
                continue
            if not message.media:
                unsupported += 1
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
                await msg.reply(f"Forward Canceled!\n\nError - {e}")
                FORWARDING[track_chat_id] = False
                break          
            forwarded += 1
            await asyncio.sleep(4)            
    except Exception as e:
        logger.exception(e)
        await msg.reply(f"Forward Canceled!\n\nError - {e}")
        if chat_id_mod:
            text = f"Target chat: {target_chat}\nSkip Msg: {current}\nGet Duplicate: {get_duplicate}\nDuplicate Search ID: {duplicate_search_id or ''}"
            try:
                await bot.edit_message_text(status_chat, status_msg_id, text)
            except MessageNotModified:
                pass
        FORWARDING[track_chat_id] = False
    else:
        await msg.edit(f'Forward Completed!\n\nTotal Messages: <code>{lst_msg_id}</code>\nCompleted Messages: <code>{current} / {lst_msg_id}</code>\nFetched Messages: <code>{fetched}</code>\nTotal Forwarded Files: <code>{forwarded}</code>\nDeleted Messages Skipped: <code>{deleted}</code>\nNon Media Files: <code>{unsupported}</code>\nDuplicate: <code>{duplicate}</code>')
        if chat_id_mod:
            text = f"Target chat: {target_chat}\nSkip Msg: {current}\nGet Duplicate: {get_duplicate}\nDuplicate Search ID: {duplicate_search_id or ''}"
            try:
                await bot.edit_message_text(status_chat, status_msg_id, text)
            except MessageNotModified:
                pass
        FORWARDING[track_chat_id] = False
        
