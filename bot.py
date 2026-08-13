# bot.py
# Main Entry Point - Telegram Forward Bot
# kurigram 2.2.24 | PyMongo 4.17.0

import asyncio
import logging
from pyrogram import Client, filters, idle
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode

from config import Config
from database import db, ensure_user, is_admin, get_user_targets
from handlers.keyboards import targets_list_keyboard

# Import all handlers (important)
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

# Silence some noisy loggers
logging.getLogger("pyrogram").setLevel(logging.WARNING)
logging.getLogger("pymongo").setLevel(logging.WARNING)


# ==================== BOT CLIENT ====================

app = Client(
    name="ForwardBot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
    plugins=dict(root="handlers"),   # optional if you prefer plugin system
    parse_mode=ParseMode.HTML,
    in_memory=True
)


# ==================== START HANDLER ====================

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
2. Configure settings for each target (Caption, Filters, Delay, Anti-Duplicate etc.)
3. Send a **message link** or **forward a message** from any source channel/group
4. Select the target → Forwarding starts automatically

**✨ Features**
• Multiple Targets (independent settings)
• Caption Template + Replacements
• Block Words / Whitelist
• Remove Links
• Custom Inline Buttons
• Media Type Filter
• Forward Tag ON/OFF
• Custom Delay
• Per-Target Anti-Duplicate
• Cancel anytime by sending `cancel`
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

    await message.reply(
        text,
        reply_markup=InlineKeyboardMarkup(buttons),
        disable_web_page_preview=True
    )


@app.on_callback_query(filters.regex(r"^(help|about)$"))
async def help_about_callback(client: Client, query):
    data = query.data

    if data == "help":
        text = """
**📖 Help Guide**

**1. Adding Targets**
• Use /targets → ➕ Add Target
• Or send /addtarget
• Give Channel/Group ID or @username
• Bot must be admin in the target channel

**2. Configuring Settings**
• Go to /targets → select a target
• Toggle features ON/OFF
• Edit Caption Template, Block Words, Whitelist, Delay, Media Types, Inline Buttons etc.

**3. Starting Forward**
• Send a post link from source
  Example: `https://t.me/c/1234567890/123`
• Or simply forward any message from source channel
• Bot will ask you to select target
• Choose one target or “Send to All”

**4. Cancel Forwarding**
Just send: `cancel`

**5. Important Notes**
• Anti-Duplicate works per target
• Delay is applied after every successful forward
• Only media types you selected will be forwarded
"""
    else:
        text = """
**ℹ️ About This Bot**

Advanced Multi-Target Telegram Forwarder

**Built with**
• kurigram 2.2.24 (Pyrogram fork)
• PyMongo 4.17.0
• Python 3.14

**Features**
• Fully per-target settings
• Clean modular architecture
• Anti-duplicate system
• Powerful caption & filter engine
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
    # Simply re-trigger start logic
    user = query.from_user
    ensure_user(user.id)

    targets = get_user_targets(user.id)
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
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    await query.answer()


# ==================== MAIN ====================

async def main():
    # Connect Database
    logger.info("Connecting to MongoDB...")
    db.connect()

    # Start Bot
    logger.info("Starting bot...")
    await app.start()
    me = await app.get_me()
    logger.info(f"Bot started as @{me.username} ({me.id})")

    # Keep alive
    await idle()

    # Cleanup
    await app.stop()
    db.close()
    logger.info("Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
