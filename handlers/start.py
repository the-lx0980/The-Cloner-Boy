# handlers/start.py

from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from bot import app
from database import ensure_user, is_admin, get_user_targets


async def send_start_menu(client: Client, user, message_or_query):
    """
    Common function to show the start menu.
    Works for both Message and CallbackQuery.
    """
    user_id = user.id
    ensure_user(user_id)

    if not is_admin(user_id):
        text = "❌ **Access Denied**\n\nYou are not authorized to use this bot."
        if isinstance(message_or_query, CallbackQuery):
            return await message_or_query.answer("Not authorized", show_alert=True)
        else:
            return await message_or_query.reply(text)

    targets = get_user_targets(user_id)

    text = f"""
**👋 Welcome {user.first_name}!**

This is an advanced **Multi-Target Forward Bot** with powerful per-target settings.

**📊 Your Stats**
├ Targets: `{len(targets)}`
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

    if isinstance(message_or_query, CallbackQuery):
        await message_or_query.message.edit_text(
            text,
            reply_markup=buttons,
            disable_web_page_preview=True
        )
        await message_or_query.answer()
    else:
        await message_or_query.reply(
            text,
            reply_markup=buttons,
            disable_web_page_preview=True
        )


@app.on_message(filters.private & filters.command("start"))
async def start_handler(client: Client, message: Message):
    await send_start_menu(client, message.from_user, message)


@app.on_callback_query(filters.regex(r"^back_to_start$"))
async def back_to_start(client: Client, query: CallbackQuery):
    await send_start_menu(client, query.from_user, query)


@app.on_callback_query(filters.regex(r"^(help|about)$"))
async def help_about_callback(client: Client, query: CallbackQuery):
    if query.data == "help":
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
