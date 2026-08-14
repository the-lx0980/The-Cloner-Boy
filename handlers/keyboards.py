# handlers/keyboards.py
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import Dict, Any, List, Optional


# ============================================================
# DASHBOARD
# ============================================================

def dashboard_keyboard() -> InlineKeyboardMarkup:
    buttons = [
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
    ]
    return InlineKeyboardMarkup(buttons)


# ============================================================
# TARGETS
# ============================================================

def targets_list_keyboard(targets: List[Dict]) -> InlineKeyboardMarkup:
    buttons = []
    for t in targets:
        title = (t.get("title") or "Unknown")[:28]
        chat_id = t["chat_id"]
        buttons.append([
            InlineKeyboardButton(
                f"🎯 {title}",
                callback_data=f"tg:open:{chat_id}"
            )
        ])

    buttons.append([
        InlineKeyboardButton("➕ Add Target", callback_data="tg:add"),
        InlineKeyboardButton("🔄 Refresh", callback_data="tg:list")
    ])
    buttons.append([
        InlineKeyboardButton("« Back to Dashboard", callback_data="dash:home")
    ])
    return InlineKeyboardMarkup(buttons)


def target_settings_keyboard(target: Dict[str, Any]) -> InlineKeyboardMarkup:
    s = target.get("settings", {})
    chat_id = target["chat_id"]

    def on_off(key: str, default: bool = False) -> str:
        return "✅ ON" if s.get(key, default) else "❌ OFF"

    buttons = [
        [InlineKeyboardButton(
            f"📝 Caption  {on_off('caption_enabled')}",
            callback_data=f"st:toggle:{chat_id}:caption_enabled"
        )],
        [InlineKeyboardButton(
            f"📄 Caption Template",
            callback_data=f"st:menu:{chat_id}:caption_template"
        )],
        [InlineKeyboardButton(
            f"🔄 Replacement  {on_off('replace_enabled')}",
            callback_data=f"st:toggle:{chat_id}:replace_enabled"
        )],
        [InlineKeyboardButton(
            f"✏️ Manage Replacements",
            callback_data=f"st:menu:{chat_id}:replacements"
        )],
        [InlineKeyboardButton(
            f"🚫 Block Words  {'✅ ON' if s.get('block_words') else '❌ OFF'}",
            callback_data=f"st:menu:{chat_id}:block_words"
        )],
        [InlineKeyboardButton(
            f"✅ Whitelist Mode  {on_off('whitelist_mode')}",
            callback_data=f"st:toggle:{chat_id}:whitelist_mode"
        )],
        [InlineKeyboardButton(
            f"📋 Manage Whitelist",
            callback_data=f"st:menu:{chat_id}:whitelist"
        )],
        [InlineKeyboardButton(
            f"🔗 Remove Links  {on_off('remove_links')}",
            callback_data=f"st:toggle:{chat_id}:remove_links"
        )],
        [InlineKeyboardButton(
            f"🔘 Inline Buttons  {'✅ ON' if s.get('inline_buttons') else '❌ OFF'}",
            callback_data=f"st:menu:{chat_id}:inline_buttons"
        )],
        [InlineKeyboardButton(
            f"🎞 Media Types",
            callback_data=f"st:menu:{chat_id}:media_types"
        )],
        [InlineKeyboardButton(
            f"↪️ Forward Tag  {on_off('forward_tag')}",
            callback_data=f"st:toggle:{chat_id}:forward_tag"
        )],
        [InlineKeyboardButton(
            f"⏱ Delay  [{s.get('delay', 1.0)}s]",
            callback_data=f"st:menu:{chat_id}:delay"
        )],
        [InlineKeyboardButton(
            f"🛡 Anti-Duplicate  {on_off('anti_duplicate', True)}",
            callback_data=f"st:toggle:{chat_id}:anti_duplicate"
        )],
        [InlineKeyboardButton(
            f"🆕 Future New Posts  {on_off('future_new_posts')}",
            callback_data=f"st:toggle:{chat_id}:future_new_posts"
        )],
        [
            InlineKeyboardButton("🗑 Delete Target", callback_data=f"tg:delete:{chat_id}"),
            InlineKeyboardButton("« Back", callback_data="tg:list")
        ]
    ]
    return InlineKeyboardMarkup(buttons)


def media_types_keyboard(target: Dict[str, Any]) -> InlineKeyboardMarkup:
    s = target.get("settings", {})
    chat_id = target["chat_id"]
    current = set(s.get("media_types", []))

    all_types = [
        ("photo", "🖼 Photo"),
        ("video", "🎬 Video"),
        ("document", "📄 Document"),
        ("audio", "🎵 Audio"),
        ("sticker", "🏷 Sticker"),
        ("animation", "🎞 Animation"),
        ("voice", "🎤 Voice"),
        ("video_note", "⏺ Video Note"),
        ("text", "📝 Text"),
    ]

    buttons = []
    for media_key, label in all_types:
        mark = "✅" if media_key in current else "❌"
        buttons.append([
            InlineKeyboardButton(
                f"{mark} {label}",
                callback_data=f"st:media:{chat_id}:{media_key}"
            )
        ])

    buttons.append([
        InlineKeyboardButton("« Back to Settings", callback_data=f"tg:open:{chat_id}")
    ])
    return InlineKeyboardMarkup(buttons)


def simple_back_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("« Back to Settings", callback_data=f"tg:open:{chat_id}")]
    ])


def confirm_delete_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes, Delete", callback_data=f"tg:confirm_delete:{chat_id}"),
            InlineKeyboardButton("❌ No", callback_data=f"tg:open:{chat_id}")
        ]
    ])


# ============================================================
# ACCOUNTS
# ============================================================

def accounts_list_keyboard(accounts: List[Dict]) -> InlineKeyboardMarkup:
    buttons = []
    for acc in accounts:
        name = (acc.get("name") or acc.get("phone") or "Unknown")[:25]
        status = acc.get("status", "active")
        status_icon = {
            "active": "🟢",
            "sleeping": "😴",
            "disabled": "🔴",
            "error": "⚠️"
        }.get(status, "⚪")

        buttons.append([
            InlineKeyboardButton(
                f"{status_icon} {name}",
                callback_data=f"acc:open:{acc['account_id']}"
            )
        ])

    buttons.append([
        InlineKeyboardButton("➕ Add Account", callback_data="acc:add"),
        InlineKeyboardButton("🔄 Refresh", callback_data="acc:list")
    ])
    buttons.append([
        InlineKeyboardButton("« Back to Dashboard", callback_data="dash:home")
    ])
    return InlineKeyboardMarkup(buttons)


def account_settings_keyboard(account: Dict[str, Any]) -> InlineKeyboardMarkup:
    account_id = account["account_id"]
    status = account.get("status", "active")
    limit = account.get("forward_limit", 500)
    sleep_min = account.get("sleep_after_limit_minutes", 30)
    forwarded = account.get("forwarded_count", 0)
    total = account.get("total_forwarded", 0)

    status_text = {
        "active": "🟢 Active",
        "sleeping": "😴 Sleeping",
        "disabled": "🔴 Disabled",
        "error": "⚠️ Error"
    }.get(status, status)

    buttons = [
        [InlineKeyboardButton(
            f"Status: {status_text}",
            callback_data=f"acc:toggle_status:{account_id}"
        )],
        [InlineKeyboardButton(
            f"🔢 Forward Limit: {limit}",
            callback_data=f"acc:set_limit:{account_id}"
        )],
        [InlineKeyboardButton(
            f"😴 Sleep After Limit: {sleep_min} min",
            callback_data=f"acc:set_sleep:{account_id}"
        )],
        [InlineKeyboardButton(
            f"📊 Stats: {forwarded}/{limit} (Total: {total})",
            callback_data=f"acc:stats:{account_id}"
        )],
        [InlineKeyboardButton(
            "🔄 Reset Cycle",
            callback_data=f"acc:reset:{account_id}"
        )],
        [
            InlineKeyboardButton("🗑 Remove", callback_data=f"acc:delete:{account_id}"),
            InlineKeyboardButton("« Back", callback_data="acc:list")
        ]
    ]
    return InlineKeyboardMarkup(buttons)


def confirm_delete_account_keyboard(account_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes, Delete", callback_data=f"acc:confirm_delete:{account_id}"),
            InlineKeyboardButton("❌ No", callback_data=f"acc:open:{account_id}")
        ]
    ])


# ============================================================
# FORWARD BOTS
# ============================================================

def bots_list_keyboard(bots: List[Dict]) -> InlineKeyboardMarkup:
    buttons = []
    for b in bots:
        name = (b.get("name") or b.get("bot_username") or "Bot")[:25]
        status = b.get("status", "active")
        icon = "🟢" if status == "active" else "🔴"

        buttons.append([
            InlineKeyboardButton(
                f"{icon} {name}",
                callback_data=f"bot:open:{b['bot_id']}"
            )
        ])

    buttons.append([
        InlineKeyboardButton("➕ Add Bot", callback_data="bot:add"),
        InlineKeyboardButton("🔄 Refresh", callback_data="bot:list")
    ])
    buttons.append([
        InlineKeyboardButton("« Back to Dashboard", callback_data="dash:home")
    ])
    return InlineKeyboardMarkup(buttons)


def bot_settings_keyboard(bot: Dict[str, Any]) -> InlineKeyboardMarkup:
    bot_id = bot["bot_id"]
    status = bot.get("status", "active")
    total = bot.get("total_forwarded", 0)

    status_text = "🟢 Active" if status == "active" else "🔴 Disabled"

    buttons = [
        [InlineKeyboardButton(
            f"Status: {status_text}",
            callback_data=f"bot:toggle_status:{bot_id}"
        )],
        [InlineKeyboardButton(
            f"📊 Total Forwarded: {total}",
            callback_data=f"bot:stats:{bot_id}"
        )],
        [
            InlineKeyboardButton("🗑 Remove", callback_data=f"bot:delete:{bot_id}"),
            InlineKeyboardButton("« Back", callback_data="bot:list")
        ]
    ]
    return InlineKeyboardMarkup(buttons)


def confirm_delete_bot_keyboard(bot_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes, Delete", callback_data=f"bot:confirm_delete:{bot_id}"),
            InlineKeyboardButton("❌ No", callback_data=f"bot:open:{bot_id}")
        ]
    ])


# ============================================================
# JOBS
# ============================================================

def jobs_list_keyboard(jobs: List[Dict]) -> InlineKeyboardMarkup:
    buttons = []
    for j in jobs:
        name = (j.get("name") or f"Job {j['job_id'][:6]}")[:28]
        status = j.get("status", "pending")
        icon = {
            "pending": "⏳",
            "running": "🟢",
            "paused": "⏸",
            "completed": "✅",
            "cancelled": "🛑",
            "failed": "❌"
        }.get(status, "⚪")

        buttons.append([
            InlineKeyboardButton(
                f"{icon} {name}",
                callback_data=f"job:open:{j['job_id']}"
            )
        ])

    buttons.append([
        InlineKeyboardButton("➕ Create Job", callback_data="job:create"),
        InlineKeyboardButton("🔄 Refresh", callback_data="job:list")
    ])
    buttons.append([
        InlineKeyboardButton("« Back to Dashboard", callback_data="dash:home")
    ])
    return InlineKeyboardMarkup(buttons)


def job_detail_keyboard(job: Dict[str, Any]) -> InlineKeyboardMarkup:
    job_id = job["job_id"]
    status = job.get("status", "pending")

    buttons = []

    if status in ["pending", "paused"]:
        buttons.append([
            InlineKeyboardButton("▶️ Start / Resume", callback_data=f"job:start:{job_id}")
        ])
    if status == "running":
        buttons.append([
            InlineKeyboardButton("⏸ Pause", callback_data=f"job:pause:{job_id}"),
            InlineKeyboardButton("🛑 Cancel", callback_data=f"job:cancel:{job_id}")
        ])

    buttons.append([
        InlineKeyboardButton("📊 Detailed Stats", callback_data=f"job:stats:{job_id}")
    ])
    buttons.append([
        InlineKeyboardButton("🗑 Delete Job", callback_data=f"job:delete:{job_id}"),
        InlineKeyboardButton("« Back", callback_data="job:list")
    ])
    return InlineKeyboardMarkup(buttons)


def confirm_delete_job_keyboard(job_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes, Delete", callback_data=f"job:confirm_delete:{job_id}"),
            InlineKeyboardButton("❌ No", callback_data=f"job:open:{job_id}")
        ]
    ])


# ============================================================
# JOB CREATION HELPERS
# ============================================================

def select_targets_keyboard(targets: List[Dict], selected: List[int]) -> InlineKeyboardMarkup:
    buttons = []
    for t in targets:
        title = (t.get("title") or "Unknown")[:25]
        chat_id = t["chat_id"]
        mark = "✅" if chat_id in selected else "⬜"
        buttons.append([
            InlineKeyboardButton(
                f"{mark} {title}",
                callback_data=f"jobcreate:toggle_target:{chat_id}"
            )
        ])

    buttons.append([
        InlineKeyboardButton("➡️ Next: Choose Method", callback_data="jobcreate:next_method")
    ])
    buttons.append([
        InlineKeyboardButton("❌ Cancel", callback_data="job:list")
    ])
    return InlineKeyboardMarkup(buttons)


def select_method_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 User Accounts", callback_data="jobcreate:method:user")],
        [InlineKeyboardButton("🤖 Forward Bot", callback_data="jobcreate:method:bot")],
        [InlineKeyboardButton("❌ Cancel", callback_data="job:list")]
    ])


def select_accounts_keyboard(accounts: List[Dict], selected: List[str]) -> InlineKeyboardMarkup:
    buttons = []
    for acc in accounts:
        name = (acc.get("name") or acc.get("phone") or "Account")[:25]
        acc_id = acc["account_id"]
        mark = "✅" if acc_id in selected else "⬜"
        buttons.append([
            InlineKeyboardButton(
                f"{mark} {name}",
                callback_data=f"jobcreate:toggle_account:{acc_id}"
            )
        ])

    buttons.append([
        InlineKeyboardButton("➡️ Continue", callback_data="jobcreate:next_options")
    ])
    buttons.append([
        InlineKeyboardButton("❌ Cancel", callback_data="job:list")
    ])
    return InlineKeyboardMarkup(buttons)


def select_bot_keyboard(bots: List[Dict]) -> InlineKeyboardMarkup:
    buttons = []
    for b in bots:
        name = (b.get("name") or b.get("bot_username") or "Bot")[:25]
        buttons.append([
            InlineKeyboardButton(
                f"🤖 {name}",
                callback_data=f"jobcreate:select_bot:{b['bot_id']}"
            )
        ])

    buttons.append([
        InlineKeyboardButton("❌ Cancel", callback_data="job:list")
    ])
    return InlineKeyboardMarkup(buttons)