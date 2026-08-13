from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from bson import ObjectId
from database.connection import db
from config import Config
import logging
import copy

logger = logging.getLogger(__name__)


# ==================== USERS ====================

async def ensure_user(user_id: int) -> Dict[str, Any]:
    """Create user if not exists, return user document"""
    user = db.users.find_one({"user_id": user_id})
    if user:
        return user
    
    now = datetime.now(timezone.utc)
    doc = {
        "user_id": user_id,
        "is_admin": user_id in Config.ADMINS,
        "created_at": now,
        "updated_at": now
    }
    db.users.insert_one(doc)
    return doc


def is_admin(user_id: int) -> bool:
    return user_id in Config.ADMINS


# ==================== TARGETS ====================

async def add_target(
    user_id: int,
    chat_id: int,
    title: str,
    username: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Add a new target channel for user.
    Returns the inserted document or None if already exists.
    """
    existing = db.targets.find_one({"user_id": user_id, "chat_id": chat_id})
    if existing:
        return None

    now = datetime.now(timezone.utc)
    doc = {
        "user_id": user_id,
        "chat_id": chat_id,
        "title": title,
        "username": username,
        "settings": copy.deepcopy(Config.DEFAULT_SETTINGS),
        "created_at": now,
        "updated_at": now
    }
    result = db.targets.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


async def get_user_targets(user_id: int) -> List[Dict[str, Any]]:
    """Get all targets of a user"""
    cursor = db.targets.find({"user_id": user_id}).sort("created_at", 1)
    return list(cursor)


async def get_target(user_id: int, chat_id: int) -> Optional[Dict[str, Any]]:
    return db.targets.find_one({"user_id": user_id, "chat_id": chat_id})


async def get_target_by_id(target_id: str | ObjectId) -> Optional[Dict[str, Any]]:
    if isinstance(target_id, str):
        target_id = ObjectId(target_id)
    return db.targets.find_one({"_id": target_id})


async def update_target_settings(
    user_id: int,
    chat_id: int,
    settings_update: Dict[str, Any]
) -> bool:
    """
    Update specific settings of a target.
    settings_update example: {"delay": 2.5, "anti_duplicate": False}
    """
    result = db.targets.update_one(
        {"user_id": user_id, "chat_id": chat_id},
        {
            "$set": {
                **{f"settings.{k}": v for k, v in settings_update.items()},
                "updated_at": datetime.now(timezone.utc)
            }
        }
    )
    return result.modified_count > 0


async def update_full_settings(
    user_id: int,
    chat_id: int,
    full_settings: Dict[str, Any]
) -> bool:
    """Replace entire settings object"""
    result = db.targets.update_one(
        {"user_id": user_id, "chat_id": chat_id},
        {
            "$set": {
                "settings": full_settings,
                "updated_at": datetime.now(timezone.utc)
            }
        }
    )
    return result.modified_count > 0


async def delete_target(user_id: int, chat_id: int) -> bool:
    """Delete target + its duplicate records"""
    result = db.targets.delete_one({"user_id": user_id, "chat_id": chat_id})
    if result.deleted_count > 0:
        # Also clean duplicates of this target
        db.duplicates.delete_many({"user_id": user_id, "target_chat_id": chat_id})
        return True
    return False


async def rename_target(user_id: int, chat_id: int, new_title: str) -> bool:
    result = db.targets.update_one(
        {"user_id": user_id, "chat_id": chat_id},
        {
            "$set": {
                "title": new_title,
                "updated_at": datetime.now(timezone.utc)
            }
        }
    )
    return result.modified_count > 0


# ==================== DUPLICATES ====================

async def is_duplicate(user_id: int, target_chat_id: int, unique_file_id: str) -> bool:
    """
    Check if this media is already forwarded to this specific target.
    """
    exists = db.duplicates.find_one({
        "user_id": user_id,
        "target_chat_id": target_chat_id,
        "unique_file_id": unique_file_id
    })
    return exists is not None


async def mark_as_forwarded(
    user_id: int,
    target_chat_id: int,
    unique_file_id: str
) -> bool:
    """
    Save unique_file_id for this user + target.
    Returns False if already exists (duplicate).
    """
    try:
        db.duplicates.insert_one({
            "user_id": user_id,
            "target_chat_id": target_chat_id,
            "unique_file_id": unique_file_id,
            "created_at": datetime.now(timezone.utc)
        })
        return True
    except Exception:
        # DuplicateKeyError means already exists
        return False


async def clear_duplicates(user_id: int, target_chat_id: int) -> int:
    """Clear all duplicate records of a specific target. Returns deleted count."""
    result = db.duplicates.delete_many({
        "user_id": user_id,
        "target_chat_id": target_chat_id
    })
    return result.deleted_count


async def get_duplicate_count(user_id: int, target_chat_id: int) -> int:
    return db.duplicates.count_documents({
        "user_id": user_id,
        "target_chat_id": target_chat_id
    })


# ==================== HELPERS ====================

def get_setting(target: Dict[str, Any], key: str, default=None):
    """Safe way to get a setting from target document"""
    return target.get("settings", {}).get(key, default)
