from pyrogram import Client
from pyrogram.enums import ParseMode
from config import Config

# Instantiate the app here so anyone can safely import it
app = Client(
    name="ForwardBot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
    parse_mode=ParseMode.HTML,
    in_memory=True
)
