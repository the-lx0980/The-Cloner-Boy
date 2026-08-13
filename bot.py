# bot.py
# Compatible with kurigram 2.2.24 + Python 3.14 + Render

import logging
from pyrogram import Client, filters, idle
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode

from config import Config
from database import db, ensure_user, is_admin, get_user_targets

# Import all handlers
from handlers import target_handlers
from handlers import settings_handlers
from handlers import text_input_handlers
from handlers import source_handler


# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

logging.getLogger("pyrogram").setLevel(logging.WARNING)
logging.getLogger("pymongo").setLevel(logging.WARNING)


# ==================== CLIENT ====================

app = Client(
    name="ForwardBot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
    parse_mode=ParseMode.HTML,
    in_memory=True
)


# ==================== HANDLERS ====================

async def send_start_menu(client, user, message_or_query):
    user_id = user.id
    ensure_user(user_id)

    if not is_admin(user_id):
        if hasattr(message_or_query, "answer"):  # CallbackQuery
            return await message_or_query.answer("❌ Not authorized", show_alert=True)
        else:
            return await message_or_query.reply("❌ **Access Denied**")

    targets = get_user_targets(user_id)

    text = f"""
**👋 Welcome {user.first_name}!**

This is an advanced **Multi-Target Forward Bot**.

**📊 Your Stats**
├ Targets: `{len(targets)}`
└ Status: `Admin`

**🛠 Commands**
/targets — Manage targets
/addtarget — Add new target
/start — This message
"""

    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎯 My Targets", callback_data="tg:list"),
            InlineKeyboardButton("➕ Add Target", callback_data="tg:add")
        ],
        [
            InlineKeyboardButton("📖 Help", callback_data="help"),
            InlineKeyboardButton("ℹ️ About", callback_data="about")
        ]
    ])

    if hasattr(message_or_query, "edit_text"):  # CallbackQuery
        await message_or_query.message.edit_text(text, reply_markup=buttons, disable_web_page_preview=True)
        await message_or_query.answer()
    else:  # Message
        await message_or_query.reply(text, reply_markup=buttons, disable_web_page_preview=True)


@app.on_message(filters.private & filters.command("start"))
async def start_handler(client: Client, message: Message):
    await send_start_menu(client, message.from_user, message)


@app.on_callback_query(filters.regex(r"^back_to_start$"))
async def back_to_start(client: Client, query):
    await send_start_menu(client, query.from_user, query)


# ==================== STARTUP ====================

if __name__ == "__main__":
    logger.info("Connecting to MongoDB...")
    try:
        db.connect()
        logger.info("✅ MongoDB connected successfully")
    except Exception as e:
        logger.error(f"❌ MongoDB connection failed: {e}")
        raise

    logger.info("Starting bot with kurigram 2.2.24...")
    app.run()   # ← YEH SAHI TARIKA HAI (no argument)
