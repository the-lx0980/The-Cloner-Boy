# handlers/settings_handlers.py

from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery
from pyrogram.enums import ParseMode

from database import (
    is_admin, get_target, update_target_settings, get_setting
)
from handlers.keyboards import (
    target_settings_keyboard, media_types_keyboard, simple_back_keyboard
)
import logging

logger = logging.getLogger(__name__)


@Client.on_callback_query(filters.regex(r"^st:"))
async def settings_callbacks(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    if not is_admin(user_id):
        return await query.answer("Not allowed", show_alert=True)

    data = query.data
    parts = data.split(":")

    # st:toggle:CHAT_ID:KEY
    if parts[1] == "toggle":
        chat_id = int(parts[2])
        key = parts[3]

        target = get_target(user_id, chat_id)
        if not target:
            return await query.answer("Target not found", show_alert=True)

        current = get_setting(target, key, False)
        new_value = not current

        update_target_settings(user_id, chat_id, {key: new_value})

        # Refresh target
        target = get_target(user_id, chat_id)
        title = target.get("title", "Unknown")

        text = (
            f"**🎯 Target Settings**\n\n"
            f"**Name:** {title}\n"
            f"**Chat ID:** `{chat_id}`\n\n"
            f"Configure all features below:"
        )
        await query.message.edit_text(text, reply_markup=target_settings_keyboard(target))
        await query.answer(f"{key.replace('_', ' ').title()} → {'ON' if new_value else 'OFF'}")
        return

    # st:menu:CHAT_ID:FEATURE
    if parts[1] == "menu":
        chat_id = int(parts[2])
        feature = parts[3]

        target = get_target(user_id, chat_id)
        if not target:
            return await query.answer("Target not found", show_alert=True)

        s = target.get("settings", {})

        if feature == "media_types":
            text = (
                f"**🎞 Media Types Filter**\n\n"
                f"Select which media types should be forwarded.\n"
                f"Only selected types will be processed."
            )
            await query.message.edit_text(text, reply_markup=media_types_keyboard(target))
            return await query.answer()

        if feature == "delay":
            current = s.get("delay", 1.0)
            text = (
                f"**⏱ Delay Settings**\n\n"
                f"Current delay: **{current} seconds**\n\n"
                f"Send a new delay value in seconds (example: `1.5` or `3`)\n\n"
                f"Type /cancel to go back."
            )
            await query.message.edit_text(text, reply_markup=simple_back_keyboard(chat_id))
            # simple state
            client.settings_state = getattr(client, "settings_state", {})
            client.settings_state[user_id] = {"action": "set_delay", "chat_id": chat_id}
            return await query.answer()

        if feature == "caption_template":
            current = s.get("caption_template", "<b>{caption}</b>")
            text = (
                f"**📄 Caption Template**\n\n"
                f"Current template:\n`{current}`\n\n"
                f"You can use `{{caption}}` placeholder.\n\n"
                f"Send new template now.\n"
                f"Type /cancel to go back."
            )
            await query.message.edit_text(text, reply_markup=simple_back_keyboard(chat_id))
            client.settings_state = getattr(client, "settings_state", {})
            client.settings_state[user_id] = {"action": "set_caption_template", "chat_id": chat_id}
            return await query.answer()

        if feature == "block_words":
            words = s.get("block_words", [])
            words_text = ", ".join(words) if words else "None"
            text = (
                f"**🚫 Block Words**\n\n"
                f"Current blocked words:\n`{words_text}`\n\n"
                f"Send words separated by comma to **replace** the list.\n"
                f"Example: `cam, sample, telegram`\n\n"
                f"Send `clear` to remove all.\n"
                f"Type /cancel to go back."
            )
            await query.message.edit_text(text, reply_markup=simple_back_keyboard(chat_id))
            client.settings_state = getattr(client, "settings_state", {})
            client.settings_state[user_id] = {"action": "set_block_words", "chat_id": chat_id}
            return await query.answer()

        if feature == "whitelist":
            words = s.get("whitelist", [])
            words_text = ", ".join(words) if words else "None"
            text = (
                f"**✅ Whitelist**\n\n"
                f"Current whitelist:\n`{words_text}`\n\n"
                f"When **Whitelist Mode** is ON, only messages containing at least one of these words will be forwarded.\n\n"
                f"Send words separated by comma to **replace** the list.\n"
                f"Example: `1080p, WEB-DL, Netflix`\n\n"
                f"Send `clear` to remove all.\n"
                f"Type /cancel to go back."
            )
            await query.message.edit_text(text, reply_markup=simple_back_keyboard(chat_id))
            client.settings_state = getattr(client, "settings_state", {})
            client.settings_state[user_id] = {"action": "set_whitelist", "chat_id": chat_id}
            return await query.answer()

        if feature == "replacements":
            reps = s.get("replacements", [])
            if reps:
                lines = [f"`{r['from']}` → `{r['to']}`" for r in reps]
                reps_text = "\n".join(lines)
            else:
                reps_text = "No replacements set."

            text = (
                f"**🔄 Text Replacements**\n\n"
                f"{reps_text}\n\n"
                f"To set replacements, send in this format:\n"
                f"`oldtext => newtext`\n"
                f"Multiple lines supported.\n\n"
                f"Example:\n"
                f"`@OldChannel => @MyChannel`\n"
                f"`cam => `   (to remove word)\n\n"
                f"Send `clear` to remove all.\n"
                f"Type /cancel to go back."
            )
            await query.message.edit_text(text, reply_markup=simple_back_keyboard(chat_id))
            client.settings_state = getattr(client, "settings_state", {})
            client.settings_state[user_id] = {"action": "set_replacements", "chat_id": chat_id}
            return await query.answer()

        if feature == "inline_buttons":
            buttons = s.get("inline_buttons", [])
            text = (
                f"**🔘 Custom Inline Buttons**\n\n"
                f"Current buttons: **{len(buttons)} row(s)**\n\n"
                f"Send buttons in this format:\n"
                f"`Button Text - https://example.com`\n\n"
                f"Multiple buttons in one row → separate by `||`\n"
                f"New row → new line\n\n"
                f"Example:\n"
                f"`📥 Download - https://link1.com || 📢 Channel - https://t.me/mychannel`\n"
                f"`🔥 More - https://link3.com`\n\n"
                f"Send `clear` to remove all buttons.\n"
                f"Type /cancel to go back."
            )
            await query.message.edit_text(text, reply_markup=simple_back_keyboard(chat_id))
            client.settings_state = getattr(client, "settings_state", {})
            client.settings_state[user_id] = {"action": "set_inline_buttons", "chat_id": chat_id}
            return await query.answer()

        await query.answer("Unknown menu", show_alert=True)
        return

    # st:media:CHAT_ID:MEDIA_KEY  (toggle media type)
    if parts[1] == "media":
        chat_id = int(parts[2])
        media_key = parts[3]

        target = get_target(user_id, chat_id)
        if not target:
            return await query.answer("Target not found", show_alert=True)

        current_list = list(get_setting(target, "media_types", []))
        if media_key in current_list:
            current_list.remove(media_key)
        else:
            current_list.append(media_key)

        update_target_settings(user_id, chat_id, {"media_types": current_list})

        # refresh
        target = get_target(user_id, chat_id)
        text = (
            f"**🎞 Media Types Filter**\n\n"
            f"Select which media types should be forwarded."
        )
        await query.message.edit_text(text, reply_markup=media_types_keyboard(target))
        await query.answer(f"{media_key} updated")
        return
