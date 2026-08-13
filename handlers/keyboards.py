# handlers/keyboards.py

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import Dict, Any, List


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