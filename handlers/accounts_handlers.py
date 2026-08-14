# handlers/accounts_handlers.py
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery
from pyrogram.enums import ParseMode

from database import (
    is_admin, ensure_user, get_user_accounts, get_account,
    add_forward_account, update_account, set_account_status,
    delete_account, reset_account_cycle, AccountStatus
)
from handlers.keyboards import (
    accounts_list_keyboard, account_settings_keyboard,
    confirm_delete_account_keyboard
)
import logging

logger = logging.getLogger(__name__)


async def show_accounts_list(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    accounts = get_user_accounts(user_id)

    if not accounts:
        text = (
            "**👤 My Accounts**\n\n"
            "You have no accounts yet.\n"
            "Click **Add Account** to authorize a new user account."
        )
    else:
        text = f"**👤 My Accounts** ({len(accounts)})\n\nSelect an account to manage:"

    await query.message.edit_text(text, reply_markup=accounts_list_keyboard(accounts))
    await query.answer()


@Client.on_callback_query(filters.regex(r"^acc:"))
async def accounts_callbacks(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    if not is_admin(user_id):
        return await query.answer("Not allowed", show_alert=True)

    data = query.data
    ensure_user(user_id)

    # -------- List --------
    if data == "acc:list":
        await show_accounts_list(client, query)
        return

    # -------- Add Account --------
    if data == "acc:add":
        await query.message.edit_text(
            "**➕ Add New Account**\n\n"
            "Send the **phone number** in international format.\n\n"
            "Example: `+919876543210`\n\n"
            "After that you will receive a login code.\n"
            "Type /cancel to cancel."
        )
        client.account_add_state = getattr(client, "account_add_state", {})
        client.account_add_state[user_id] = {"step": "phone"}
        return await query.answer()

    # -------- Open Account --------
    if data.startswith("acc:open:"):
        account_id = data.split(":")[2]
        account = get_account(user_id, account_id)
        if not account:
            return await query.answer("Account not found", show_alert=True)

        name = account.get("name") or account.get("phone")
        status = account.get("status", "active")
        limit = account.get("forward_limit", 500)
        sleep_min = account.get("sleep_after_limit_minutes", 30)
        forwarded = account.get("forwarded_count", 0)
        total = account.get("total_forwarded", 0)

        text = (
            f"**👤 Account Settings**\n\n"
            f"**Name:** {name}\n"
            f"**Phone:** `{account.get('phone')}`\n"
            f"**Status:** `{status}`\n"
            f"**Forward Limit:** `{limit}`\n"
            f"**Sleep After Limit:** `{sleep_min} min`\n"
            f"**Current Cycle:** `{forwarded}/{limit}`\n"
            f"**Total Forwarded:** `{total}`\n"
        )
        await query.message.edit_text(text, reply_markup=account_settings_keyboard(account))
        return await query.answer()

    # -------- Toggle Status --------
    if data.startswith("acc:toggle_status:"):
        account_id = data.split(":")[2]
        account = get_account(user_id, account_id)
        if not account:
            return await query.answer("Account not found", show_alert=True)

        current = account.get("status")
        new_status = AccountStatus.DISABLED.value if current == AccountStatus.ACTIVE.value else AccountStatus.ACTIVE.value
        set_account_status(user_id, account_id, new_status)

        account = get_account(user_id, account_id)
        await query.message.edit_text(
            f"**👤 Account Settings**\n\nStatus updated to `{new_status}`",
            reply_markup=account_settings_keyboard(account)
        )
        return await query.answer(f"Status → {new_status}")

    # -------- Set Limit --------
    if data.startswith("acc:set_limit:"):
        account_id = data.split(":")[2]
        await query.message.edit_text(
            "**🔢 Set Forward Limit**\n\n"
            "Send the maximum number of messages this account can forward before sleeping.\n\n"
            "Example: `500`\n\n"
            "Type /cancel to go back."
        )
        client.account_edit_state = getattr(client, "account_edit_state", {})
        client.account_edit_state[user_id] = {"action": "set_limit", "account_id": account_id}
        return await query.answer()

    # -------- Set Sleep --------
    if data.startswith("acc:set_sleep:"):
        account_id = data.split(":")[2]
        await query.message.edit_text(
            "**😴 Set Sleep Time**\n\n"
            "Send how many minutes the account should sleep after reaching the limit.\n\n"
            "Example: `30`\n\n"
            "Type /cancel to go back."
        )
        client.account_edit_state = getattr(client, "account_edit_state", {})
        client.account_edit_state[user_id] = {"action": "set_sleep", "account_id": account_id}
        return await query.answer()

    # -------- Reset Cycle --------
    if data.startswith("acc:reset:"):
        account_id = data.split(":")[2]
        reset_account_cycle(user_id, account_id)
        account = get_account(user_id, account_id)
        await query.answer("Cycle reset", show_alert=True)
        await query.message.edit_text(
            "**👤 Account Settings**\n\nCycle has been reset.",
            reply_markup=account_settings_keyboard(account)
        )
        return

    # -------- Delete --------
    if data.startswith("acc:delete:"):
        account_id = data.split(":")[2]
        account = get_account(user_id, account_id)
        if not account:
            return await query.answer("Account not found", show_alert=True)

        await query.message.edit_text(
            f"**⚠️ Delete Account?**\n\n"
            f"**{account.get('name')}** (`{account.get('phone')}`)\n\n"
            f"This action cannot be undone.",
            reply_markup=confirm_delete_account_keyboard(account_id)
        )
        return await query.answer()

    if data.startswith("acc:confirm_delete:"):
        account_id = data.split(":")[2]
        success = delete_account(user_id, account_id)
        if success:
            await query.answer("✅ Account deleted", show_alert=True)
            await show_accounts_list(client, query)
        else:
            await query.answer("Failed to delete", show_alert=True)
        return