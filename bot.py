# bot.py
# Fixed version for Python 3.14 + Render / kurigram

import logging
from pyrogram import Client, filters, idle
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode

from config import Config
from database import db, ensure_user, is_admin, get_user_targets

# Import handlers
from handlers import target_handlers
from handlers import settings_handlers
from handlers import text_input_handlers
from handlers import source_handler

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

logging.getLogger("pyrogram").setLevel(logging.WARNING)
logging.getLogger("pymongo").setLevel(logging.WARNING)


app = Client(
    name="ForwardBot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
    parse_mode=ParseMode.HTML,
    in_memory=True
)


@app.on_message(filters.private & filters.command("start"))
async def start_handler(client: Client, message: Message):
    user = message.from_user
    user_id = user.id

    ensure_user(user_id)

    if not is_admin(user_id):
        return await message.reply(
            "❌ **Access Denied**\n\n"
            "You are not authorized to use this bot."
        )

    targets = get_user_targets(user_id)
    total_targets = len(targets)

    text = f"""
**👋 Welcome {user.first_name}!**

This is an advanced **Multi-Target Forward Bot** with powerful per-target settings.

**📊 Your Stats**
├ Targets: `{total_targets}`
└ Status: `Admin`

**🛠 Main Commands**
/targets — Manage your target channels
/addtarget — Quickly add a new target
/start — Show this message

**🚀 How to Forward**
1. Add one or more target channels using /targets
2. Configure settings for each target
3. Send a **message link** or **forward a message** from any source
4. Select the target → Forwarding starts
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
    data = query.data

    if data == "help":
        text = """
**📖 Help Guide**

**1. Adding Targets**
• /targets → ➕ Add Target
• Bot must be admin in target channel

**2. Configuring Settings**
• /targets → select a target
• Toggle features & edit values

**3. Starting Forward**
• Send post link or forward a message
• Select target

**4. Cancel**
Send: `cancel`
"""
    else:
        text = """
**ℹ️ About**

Advanced Multi-Target Telegram Forwarder

• kurigram 2.2.24
• PyMongo 4.17.0
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
    ensure_user(user.id)
    targets = get_user_targets(user.id)

    text = f"""
**👋 Welcome {user.first_name}!**

**📊 Your Stats**
├ Targets: `{len(targets)}`
└ Status: `Admin`

**🛠 Main Commands**
/targets — Manage targets
/addtarget — Add new target
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

    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    await query.answer()


# ==================== STARTUP ====================

async def start_bot():
    logger.info("Connecting to MongoDB...")
    db.connect()
    logger.info("MongoDB connected")

    logger.info("Starting Telegram client...")
    await app.start()
    me = await app.get_me()
    logger.info(f"Bot started as @{me.username} (ID: {me.id})")

    await idle()          # Keep running

    await app.stop()
    db.close()
    logger.info("Bot stopped.")


if __name__ == "__main__":
    # Ye sabse stable tarika hai
    app.run(start_bot())
