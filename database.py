# database.py
# Complete Database Layer for Telegram Forward Bot
# PyMongo 4.17.0 | Compatible with kurigram 2.2.24

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from bson import ObjectId
from pymongo import MongoClient, ASCENDING
from pymongo.database import Database as MongoDatabase
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError
import copy
import logging

from config import Config

logger = logging.getLogger(__name__)


class Database:
    def __init__(self):
        self.client: Optional[MongoClient] = None
        self.db: Optional[MongoDatabase] = None

        self.users: Optional[Collection] = None
        self.targets: Optional[Collection] = None
        self.duplicates: Optional[Collection] = None

    def connect(self) -> None:
        """Connect to MongoDB and create indexes."""
        try:
            self.client = MongoClient(
                Config.MONGO_URI,
                serverSelectionTimeoutMS=5000
            )
            # Force connection check
            self.client.admin.command("ping")

            self.db = self.client[Config.DB_NAME]

            self.users = self.db["users"]
            self.targets = self.db["targets"]
            self.duplicates = self.db["duplicates"]

            self._create_indexes()
            logger.info("✅ MongoDB connected successfully")

        except Exception as e:
            logger.error(f"❌ MongoDB connection failed: {e}")
            raise

    def _create_indexes(self) -> None:
        """Create all required indexes."""
        # users
        self.users.create_index([("user_id", ASCENDING)], unique=True)

        # targets
        self.targets.create_index([("user_id", ASCENDING)])
        self.targets.create_index(
            [("user_id", ASCENDING), ("chat_id", ASCENDING)],
            unique=True
        )

        # duplicates - most important for performance + uniqueness
        self.duplicates.create_index(
            [
                ("user_id", ASCENDING),
                ("target_chat_id", ASCENDING),
                ("unique_file_id", ASCENDING)
            ],
            unique=True
        )

        logger.info("✅ Database indexes created")

    def close(self) -> None:
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")


# Global instance
db = Database()


# ============================================================
# USERS
# ============================================================

def ensure_user(user_id: int) -> Dict[str, Any]:
    """Create user if not exists and return the document."""
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
    """Check if user is in Config.ADMINS."""
    return user_id in Config.ADMINS


# ============================================================
# TARGETS
# ============================================================

def add_target(
    user_id: int,
    chat_id: int,
    title: str,
    username: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Add a new target for the user.
    Returns the new document or None if already exists.
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


def get_user_targets(user_id: int) -> List[Dict[str, Any]]:
    """Return all targets of a user sorted by creation time."""
    cursor = db.targets.find({"user_id": user_id}).sort("created_at", 1)
    return list(cursor)


def get_target(user_id: int, chat_id: int) -> Optional[Dict[str, Any]]:
    """Get a specific target of a user."""
    return db.targets.find_one({"user_id": user_id, "chat_id": chat_id})


def get_target_by_id(target_id: str | ObjectId) -> Optional[Dict[str, Any]]:
    """Get target by MongoDB _id."""
    if isinstance(target_id, str):
        try:
            target_id = ObjectId(target_id)
        except Exception:
            return None
    return db.targets.find_one({"_id": target_id})


def update_target_settings(
    user_id: int,
    chat_id: int,
    settings_update: Dict[str, Any]
) -> bool:
    """
    Update one or more settings of a target.
    Example: settings_update = {"delay": 2.0, "anti_duplicate": False}
    """
    set_fields = {f"settings.{k}": v for k, v in settings_update.items()}
    set_fields["updated_at"] = datetime.now(timezone.utc)

    result = db.targets.update_one(
        {"user_id": user_id, "chat_id": chat_id},
        {"$set": set_fields}
    )
    return result.modified_count > 0


def update_full_settings(
    user_id: int,
    chat_id: int,
    full_settings: Dict[str, Any]
) -> bool:
    """Replace the entire settings object of a target."""
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


def delete_target(user_id: int, chat_id: int) -> bool:
    """
    Delete a target and also delete all its duplicate records.
    """
    result = db.targets.delete_one({"user_id": user_id, "chat_id": chat_id})
    if result.deleted_count > 0:
        db.duplicates.delete_many({
            "user_id": user_id,
            "target_chat_id": chat_id
        })
        return True
    return False


def rename_target(user_id: int, chat_id: int, new_title: str) -> bool:
    """Rename a target."""
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


# ============================================================
# DUPLICATES (Per Target)
# ============================================================

def is_duplicate(user_id: int, target_chat_id: int, unique_file_id: str) -> bool:
    """
    Check if this unique_file_id is already forwarded
    to this specific target by this user.
    """
    doc = db.duplicates.find_one({
        "user_id": user_id,
        "target_chat_id": target_chat_id,
        "unique_file_id": unique_file_id
    })
    return doc is not None


def mark_as_forwarded(
    user_id: int,
    target_chat_id: int,
    unique_file_id: str
) -> bool:
    """
    Save unique_file_id for this user + target.
    Returns True if inserted successfully.
    Returns False if it already exists (DuplicateKeyError).
    """
    try:
        db.duplicates.insert_one({
            "user_id": user_id,
            "target_chat_id": target_chat_id,
            "unique_file_id": unique_file_id,
            "created_at": datetime.now(timezone.utc)
        })
        return True
    except DuplicateKeyError:
        return False
    except Exception as e:
        logger.error(f"Error marking duplicate: {e}")
        return False


def clear_duplicates(user_id: int, target_chat_id: int) -> int:
    """
    Clear all duplicate records of a specific target.
    Returns number of deleted documents.
    """
    result = db.duplicates.delete_many({
        "user_id": user_id,
        "target_chat_id": target_chat_id
    })
    return result.deleted_count


def get_duplicate_count(user_id: int, target_chat_id: int) -> int:
    """Return how many unique files are already marked for this target."""
    return db.duplicates.count_documents({
        "user_id": user_id,
        "target_chat_id": target_chat_id
    })


# ============================================================
# HELPERS
# ============================================================

def get_setting(target: Dict[str, Any], key: str, default: Any = None) -> Any:
    """Safe getter for a setting inside target document."""
    return target.get("settings", {}).get(key, default)
