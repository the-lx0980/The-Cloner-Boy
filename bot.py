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

@app.on_message(filters.private & filters.command("start"))
async def start_handler(client: Client, message: Message):
    user = message.from_user
    user_id = user.id

    ensure_user(user_id)

    if not is_admin(user_id):
        return await message.reply(
            "❌ **Access Denied**\n\nYou are not authorized to use this bot."
        )

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

**How to use**
1. Add targets via /targets
2. Configure settings for each target
3. Send source link or forward a message
4. Select target → Forwarding starts
"""

    buttons = [
        [
            InlineKeyboardButton("🎯 My Targets", callback_data="tg:list"),
            InlineKeyboardButton("➕ Add Target", callback_data="tg:add")
        ],
        [
            InlineKeyboardButton("📖 Help", callback_data="help"),
            InlineKeyboardButton("ℹ️ About", callback_data="about")
        ]
    ]

    await message.reply(text, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True)


@app.on_callback_query(filters.regex(r"^(help|about)$"))
async def help_about_callback(client: Client, query):
    if query.data == "help":
        text = """
**📖 Help**

• /targets → Manage & configure targets
• Send source link or forward message
• Select target to start forwarding
• Send `cancel` to stop ongoing process
"""
    else:
        text = """
**ℹ️ About**

Multi-Target Forward Bot
• kurigram 2.2.24
• Per-target settings
• Anti-duplicate system
"""

    await query.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("« Back", callback_data="back_to_start")]
        ])
    )
    await query.answer()


@app.on_callback_query(filters.regex(r"^back_to_start$"))
async def back_to_start(client: Client, query):
    user = query.from_user
    user_id = user.id

    ensure_user(user_id)

    if not is_admin(user_id):
        return await query.answer("❌ You are not authorized.", show_alert=True)

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

**How to use**
1. Add targets via /targets
2. Configure settings for each target
3. Send source link or forward a message
4. Select target → Forwarding starts
"""

    buttons = [
        [
            InlineKeyboardButton("🎯 My Targets", callback_data="tg:list"),
            InlineKeyboardButton("➕ Add Target", callback_data="tg:add")
        ],
        [
            InlineKeyboardButton("📖 Help", callback_data="help"),
            InlineKeyboardButton("ℹ️ About", callback_data="about")
        ]
    ]

    await query.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(buttons),
        disable_web_page_preview=True
    )
    await query.answer()


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
