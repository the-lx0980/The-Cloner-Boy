# handlers/accounts_handlers.py
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery
from pyrogram.enums import ParseMode
from pyrogram.errors import (
    PhoneCodeInvalid, PhoneCodeExpired, SessionPasswordNeeded,
    PhoneNumberInvalid, FloodWait
)

from database import (
    is_admin, ensure_user,
    get_user_accounts, get_account,
    add_forward_account, update_account,
    set_account_status, delete_account,
    reset_account_cycle, AccountStatus
)
from handlers.keyboards import (
    accounts_list_keyboard,
    account_settings_keyboard,
    confirm_delete_account_keyboard
)
import logging

logger = logging.getLogger(__name__)


async def show_accounts_list(client: Client, query: CallbackQuery):
    """Show list of all user accounts"""
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

    # -------------------- List --------------------
    if data == "acc:list":
        await show_accounts_list(client, query)
        return

    # -------------------- Add Account (Start Login Flow) --------------------
    if data == "acc:add":
        await query.message.edit_text(
            "**➕ Add New Account**\n\n"
            "Send the **phone number** in international format.\n\n"
            "Example: `+919876543210`\n\n"
            "Type /cancel to cancel."
        )
        client.account_add_state = getattr(client, "account_add_state", {})
        client.account_add_state[user_id] = {"step": "phone"}
        return await query.answer()

    # -------------------- Open Account --------------------
    if data.startswith("acc:open:"):
        account_id = data.split(":")[2]
        account = get_account(user_id, account_id)
        if not account:
            return await query.answer("Account not found", show_alert=True)

        name = account.get("name") or account.get("phone") or "Unknown"
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
            f"**Total Forwarded:** `{total}`"
        )
        await query.message.edit_text(
            text,
            reply_markup=account_settings_keyboard(account)
        )
        return await query.answer()

    # -------------------- Toggle Status --------------------
    if data.startswith("acc:toggle_status:"):
        account_id = data.split(":")[2]
        account = get_account(user_id, account_id)
        if not account:
            return await query.answer("Account not found", show_alert=True)

        current = account.get("status", "active")
        if current == AccountStatus.ACTIVE.value:
            new_status = AccountStatus.DISABLED.value
        else:
            new_status = AccountStatus.ACTIVE.value

        set_account_status(user_id, account_id, new_status)
        account = get_account(user_id, account_id)

        await query.message.edit_text(
            f"**👤 Account Settings**\n\nStatus updated to `{new_status}`",
            reply_markup=account_settings_keyboard(account)
        )
        return await query.answer(f"Status → {new_status}")

    # -------------------- Set Forward Limit --------------------
    if data.startswith("acc:set_limit:"):
        account_id = data.split(":")[2]
        await query.message.edit_text(
            "**🔢 Set Forward Limit**\n\n"
            "Send the maximum number of messages this account can forward "
            "before going to sleep.\n\n"
            "Example: `500`\n\n"
            "Type /cancel to go back."
        )
        client.account_edit_state = getattr(client, "account_edit_state", {})
        client.account_edit_state[user_id] = {
            "action": "set_limit",
            "account_id": account_id
        }
        return await query.answer()

    # -------------------- Set Sleep Time --------------------
    if data.startswith("acc:set_sleep:"):
        account_id = data.split(":")[2]
        await query.message.edit_text(
            "**😴 Set Sleep Time**\n\n"
            "Send how many **minutes** the account should sleep "
            "after reaching the forward limit.\n\n"
            "Example: `30`\n\n"
            "Type /cancel to go back."
        )
        client.account_edit_state = getattr(client, "account_edit_state", {})
        client.account_edit_state[user_id] = {
            "action": "set_sleep",
            "account_id": account_id
        }
        return await query.answer()

    # -------------------- Reset Cycle --------------------
    if data.startswith("acc:reset:"):
        account_id = data.split(":")[2]
        reset_account_cycle(user_id, account_id)
        account = get_account(user_id, account_id)

        await query.answer("✅ Cycle reset successfully", show_alert=True)
        await query.message.edit_text(
            "**👤 Account Settings**\n\nCycle has been reset.",
            reply_markup=account_settings_keyboard(account)
        )
        return

    # -------------------- Delete Account --------------------
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

    # -------------------- Confirm Delete --------------------
    if data.startswith("acc:confirm_delete:"):
        account_id = data.split(":")[2]
        success = delete_account(user_id, account_id)

        if success:
            await query.answer("✅ Account deleted", show_alert=True)
            await show_accounts_list(client, query)
        else:
            await query.answer("Failed to delete", show_alert=True)
        return


# -------------------- Phone Number Input Handler --------------------
@Client.on_message(filters.private & filters.text)
async def account_add_phone_handler(client: Client, message: Message):
    """Handle phone number input for adding new account"""
    user_id = message.from_user.id
    
    # Check if user is in phone input state
    account_add_state = getattr(client, "account_add_state", {})
    if user_id not in account_add_state:
        return
    
    state = account_add_state[user_id]
    if state.get("step") != "phone":
        return
    
    # Cancel command
    if message.text.startswith("/cancel"):
        del account_add_state[user_id]
        await message.reply_text("❌ Cancelled account addition.")
        return
    
    phone = message.text.strip()
    
    # Validate phone format
    if not phone.startswith("+") or not phone[1:].isdigit():
        await message.reply_text(
            "❌ Invalid phone number format.\n\n"
            "Please send phone number in international format.\n"
            "Example: `+919876543210`\n\n"
            "Type /cancel to cancel."
        )
        return
    
    try:
        # Try to send login code
        sent_code = await client.send_code(phone)
        
        # Store session data
        client.account_add_state[user_id] = {
            "step": "code",
            "phone": phone,
            "phone_code_hash": sent_code.phone_code_hash
        }
        
        await message.reply_text(
            "**📱 Verification Code Sent**\n\n"
            f"A login code has been sent to `{phone}`.\n\n"
            "Please send the code you received (numbers only).\n\n"
            "Example: `12345`\n\n"
            "Type /cancel to cancel."
        )
        
    except PhoneNumberInvalid:
        await message.reply_text(
            "❌ Invalid phone number.\n\n"
            "Please send a valid phone number in international format.\n"
            "Example: `+919876543210`\n\n"
            "Type /cancel to cancel."
        )
    except FloodWait as e:
        wait_time = e.value
        await message.reply_text(
            f"⏳ **Rate Limited**\n\n"
            f"Please wait **{wait_time} seconds** before trying again."
        )
    except Exception as e:
        logger.error(f"Error sending verification code: {e}")
        await message.reply_text(
            "❌ Failed to send verification code.\n\n"
            "Please try again later."
        )


# -------------------- Code Verification Handler --------------------
@Client.on_message(filters.private & filters.text)
async def account_add_code_handler(client: Client, message: Message):
    """Handle verification code input for adding new account"""
    user_id = message.from_user.id
    
    # Check if user is in code input state
    account_add_state = getattr(client, "account_add_state", {})
    if user_id not in account_add_state:
        return
    
    state = account_add_state[user_id]
    if state.get("step") != "code":
        return
    
    # Cancel command
    if message.text.startswith("/cancel"):
        del account_add_state[user_id]
        await message.reply_text("❌ Cancelled account addition.")
        return
    
    code = message.text.strip()
    
    # Validate code format (only numbers)
    if not code.isdigit():
        await message.reply_text(
            "❌ Invalid code format.\n\n"
            "Please send only the numeric code you received.\n"
            "Example: `12345`\n\n"
            "Type /cancel to cancel."
        )
        return
    
    try:
        phone = state.get("phone")
        phone_code_hash = state.get("phone_code_hash")
        
        # Try to sign in with the code
        try:
            await client.sign_in(phone, phone_code_hash, code)
        except SessionPasswordNeeded:
            # 2FA is enabled
            client.account_add_state[user_id] = {
                "step": "password",
                "phone": phone,
                "phone_code_hash": phone_code_hash
            }
            await message.reply_text(
                "**🔐 Two-Factor Authentication Required**\n\n"
                "This account has 2FA enabled.\n"
                "Please send your 2FA password.\n\n"
                "Type /cancel to cancel."
            )
            return
        
        # Successfully logged in
        # Get account info
        me = await client.get_me()
        account_id = f"acc_{user_id}_{me.id}"
        
        # Store account in database
        account_data = {
            "id": account_id,
            "user_id": user_id,
            "phone": phone,
            "name": me.first_name or "Unknown",
            "username": me.username,
            "status": "active",
            "forward_limit": 500,
            "sleep_after_limit_minutes": 30,
            "forwarded_count": 0,
            "total_forwarded": 0
        }
        
        add_forward_account(user_id, account_data)
        
        # Clean up state
        del account_add_state[user_id]
        
        await message.reply_text(
            f"**✅ Account Added Successfully!**\n\n"
            f"**Name:** {me.first_name or 'Unknown'}\n"
            f"**Phone:** `{phone}`\n"
            f"**Username:** @{me.username if me.username else 'N/A'}\n\n"
            f"The account has been added and is ready to use.\n"
            f"You can adjust settings using the account menu."
        )
        
        # Show accounts list
        # Note: We can't use query here, so we'll send a new message with the list
        accounts = get_user_accounts(user_id)
        await message.reply_text(
            f"**👤 My Accounts** ({len(accounts)})\n\nSelect an account to manage:",
            reply_markup=accounts_list_keyboard(accounts)
        )
        
    except PhoneCodeInvalid:
        await message.reply_text(
            "❌ Invalid verification code.\n\n"
            "Please check the code and try again.\n"
            "Type /cancel to cancel."
        )
    except PhoneCodeExpired:
        await message.reply_text(
            "❌ Verification code expired.\n\n"
            "Please start the process again by clicking **Add Account**."
        )
        del account_add_state[user_id]
    except FloodWait as e:
        wait_time = e.value
        await message.reply_text(
            f"⏳ **Rate Limited**\n\n"
            f"Please wait **{wait_time} seconds** before trying again."
        )
    except Exception as e:
        logger.error(f"Error verifying code: {e}")
        await message.reply_text(
            "❌ Failed to verify code.\n\n"
            "Please try again later."
        )
        # Clean up state on error
        if user_id in account_add_state:
            del account_add_state[user_id]


# -------------------- Password Handler (for 2FA) --------------------
@Client.on_message(filters.private & filters.text)
async def account_add_password_handler(client: Client, message: Message):
    """Handle 2FA password input for adding new account"""
    user_id = message.from_user.id
    
    # Check if user is in password input state
    account_add_state = getattr(client, "account_add_state", {})
    if user_id not in account_add_state:
        return
    
    state = account_add_state[user_id]
    if state.get("step") != "password":
        return
    
    # Cancel command
    if message.text.startswith("/cancel"):
        del account_add_state[user_id]
        await message.reply_text("❌ Cancelled account addition.")
        return
    
    password = message.text.strip()
    
    try:
        phone = state.get("phone")
        phone_code_hash = state.get("phone_code_hash")
        
        # Try to sign in with password
        await client.sign_in(phone, phone_code_hash, password)
        
        # Successfully logged in
        me = await client.get_me()
        account_id = f"acc_{user_id}_{me.id}"
        
        # Store account in database
        account_data = {
            "id": account_id,
            "user_id": user_id,
            "phone": phone,
            "name": me.first_name or "Unknown",
            "username": me.username,
            "status": "active",
            "forward_limit": 500,
            "sleep_after_limit_minutes": 30,
            "forwarded_count": 0,
            "total_forwarded": 0
        }
        
        add_forward_account(user_id, account_data)
        
        # Clean up state
        del account_add_state[user_id]
        
        await message.reply_text(
            f"**✅ Account Added Successfully!**\n\n"
            f"**Name:** {me.first_name or 'Unknown'}\n"
            f"**Phone:** `{phone}`\n"
            f"**Username:** @{me.username if me.username else 'N/A'}\n\n"
            f"The account has been added and is ready to use.\n"
            f"You can adjust settings using the account menu."
        )
        
        # Show accounts list
        accounts = get_user_accounts(user_id)
        await message.reply_text(
            f"**👤 My Accounts** ({len(accounts)})\n\nSelect an account to manage:",
            reply_markup=accounts_list_keyboard(accounts)
        )
        
    except Exception as e:
        logger.error(f"Error verifying password: {e}")
        await message.reply_text(
            "❌ Invalid password.\n\n"
            "Please try again or type /cancel to cancel."
        )