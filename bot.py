# bot.py
# Management Bot - Updated for Multi-Account + Jobs Architecture
# kurigram 2.2.24 | Python 3.14 | PyMongo 4.17.0

import logging
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode

from config import Config
from database import db, ensure_user, is_admin, get_dashboard_counts

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
    name="ManagementBot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
    parse_mode=ParseMode.HTML,
    in_memory=True,
    plugins=dict(root="handlers")          # All handlers are loaded from handlers/
)


# ==================== HELPERS ====================
def build_dashboard_text(user_id: int, first_name: str = "Admin") -> str:
    counts = get_dashboard_counts(user_id)
    return f"""
**👋 Welcome {first_name}!**

╭────────────────────────╮
│     📊 **Dashboard**      │
├────────────────────────┤
│ 🎯 Targets: **{counts['targets']}**
│ 👤 Accounts: **{counts['accounts']}**
│ 🤖 Forward Bots: **{counts['bots']}**
│ 📋 Active Jobs: **{counts['active_jobs']}**
│ 🛡 Duplicates: **{counts['duplicates']:,}**
╰────────────────────────╯

Select an option below to manage everything:
"""


def dashboard_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎯 Targets", callback_data="dash:targets"),
            InlineKeyboardButton("👤 Accounts", callback_data="dash:accounts"),
        ],
        [
            InlineKeyboardButton("🤖 Forward Bots", callback_data="dash:bots"),
            InlineKeyboardButton("📋 Jobs", callback_data="dash:jobs"),
        ],
        [
            InlineKeyboardButton("📊 Statistics", callback_data="dash:stats"),
            InlineKeyboardButton("⚙️ Settings", callback_data="dash:settings"),
        ],
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="dash:refresh"),
        ]
    ])


# ==================== /start ====================
@app.on_message(filters.private & filters.command("start"))
async def start_handler(client: Client, message: Message):
    user = message.from_user
    user_id = user.id

    ensure_user(user_id)

    if not is_admin(user_id):
        return await message.reply(
            "❌ **Access Denied**\n\nYou are not authorized to use this bot."
        )

    text = build_dashboard_text(user_id, user.first_name)
    await message.reply(
        text,
        reply_markup=dashboard_keyboard(),
        disable_web_page_preview=True
    )


# ==================== DASHBOARD CALLBACKS ====================
# (These are also available in handlers/dashboard.py, 
#  but kept here so /start works even if plugins load order changes)

@app.on_callback_query(filters.regex(r"^dash:"))
async def dashboard_callbacks(client: Client, query: CallbackQuery):
    user_id = query.from_user.id

    if not is_admin(user_id):
        return await query.answer("Not allowed", show_alert=True)

    data = query.data

    if data in ["dash:home", "dash:refresh"]:
        text = build_dashboard_text(user_id, query.from_user.first_name)
        await query.message.edit_text(
            text,
            reply_markup=dashboard_keyboard(),
            disable_web_page_preview=True
        )
        return await query.answer()

    try:
        if data == "dash:targets":
            from handlers.target_handlers import cmd_targets_internal
            await cmd_targets_internal(client, query)
            return

        if data == "dash:accounts":
            from handlers.accounts_handlers import show_accounts_list
            await show_accounts_list(client, query)
            return

        if data == "dash:bots":
            from handlers.bots_handlers import show_bots_list
            await show_bots_list(client, query)
            return

        if data == "dash:jobs":
            from handlers.jobs_handlers import show_jobs_list
            await show_jobs_list(client, query)
            return

    except ImportError as e:
        logger.error(f"Import error in dashboard: {e}")
        await query.answer("Module not loaded yet. Please restart the bot.", show_alert=True)
        return

    if data == "dash:stats":
        counts = get_dashboard_counts(user_id)
        text = f"""
**📊 Statistics Overview**

🎯 Targets: `{counts['targets']}`
👤 Accounts: `{counts['accounts']}`
🤖 Forward Bots: `{counts['bots']}`
📋 Active Jobs: `{counts['active_jobs']}`
🛡 Total Duplicates Tracked: `{counts['duplicates']:,}`
"""
        await query.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("« Back to Dashboard", callback_data="dash:home")]
            ])
        )
        return await query.answer()

    if data == "dash:settings":
        await query.answer("Global settings coming soon!", show_alert=True)
        return


# ==================== HELP / ABOUT (optional) ====================
@app.on_callback_query(filters.regex(r"^(help|about)$"))
async def help_about_callback(client: Client, query: CallbackQuery):
    if query.data == "help":
        text = """
**📖 Help**

• Use the **Dashboard** buttons to manage everything
• **Targets** → Add channels/groups + configure filters
• **Accounts** → Add user accounts for high-volume forwarding
• **Forward Bots** → Add extra bots
• **Jobs** → Create and control forwarding jobs

Send `cancel` anytime to stop an ongoing process.
"""
    else:
        text = """
**ℹ️ About**

Advanced Multi-Target Forward Management Bot
• kurigram 2.2.24
• Multi User-Account support
• Per-target settings + Anti-Duplicate
• Job system with limits & sleep timers
"""

    await query.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("« Back to Dashboard", callback_data="dash:home")]
        ])
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

    logger.info("Starting Management Bot with kurigram 2.2.24...")
    app.run()
