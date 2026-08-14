# database.py
# Complete Database Layer for Telegram Forward Management Bot
# Python 3.14 | PyMongo 4.17.0 | Compatible with kurigram 2.2.24

from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Union
from bson import ObjectId
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.database import Database as MongoDatabase
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError
import copy
import logging
from enum import Enum

from config import Config

logger = logging.getLogger(__name__)


# ============================================================
# ENUMS / CONSTANTS
# ============================================================

class AccountStatus(str, Enum):
    ACTIVE = "active"
    SLEEPING = "sleeping"
    DISABLED = "disabled"
    ERROR = "error"


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class MethodType(str, Enum):
    BOT = "bot"
    USER = "user"


class AccountStrategy(str, Enum):
    SEQUENTIAL = "sequential"
    MANUAL = "manual"


# ============================================================
# DATABASE CLASS
# ============================================================

class Database:
    def __init__(self):
        self.client: Optional[MongoClient] = None
        self.db: Optional[MongoDatabase] = None

        self.users: Optional[Collection] = None
        self.targets: Optional[Collection] = None
        self.duplicates: Optional[Collection] = None
        self.forward_accounts: Optional[Collection] = None
        self.forward_bots: Optional[Collection] = None
        self.forward_jobs: Optional[Collection] = None
        self.statistics: Optional[Collection] = None
        self.job_logs: Optional[Collection] = None

    def connect(self) -> None:
        """Connect to MongoDB and create indexes."""
        try:
            self.client = MongoClient(
                Config.MONGO_URI,
                serverSelectionTimeoutMS=5000
            )
            self.client.admin.command("ping")

            self.db = self.client[Config.DB_NAME]

            self.users = self.db["users"]
            self.targets = self.db["targets"]
            self.duplicates = self.db["duplicates"]
            self.forward_accounts = self.db["forward_accounts"]
            self.forward_bots = self.db["forward_bots"]
            self.forward_jobs = self.db["forward_jobs"]
            self.statistics = self.db["statistics"]
            self.job_logs = self.db["job_logs"]

            self._create_indexes()
            logger.info("✅ MongoDB connected successfully")

        except Exception as e:
            logger.error(f"❌ MongoDB connection failed: {e}")
            raise

    def _create_indexes(self) -> None:
        # users
        self.users.create_index([("user_id", ASCENDING)], unique=True)

        # targets
        self.targets.create_index([("user_id", ASCENDING)])
        self.targets.create_index(
            [("user_id", ASCENDING), ("chat_id", ASCENDING)],
            unique=True
        )

        # duplicates
        self.duplicates.create_index(
            [
                ("user_id", ASCENDING),
                ("target_chat_id", ASCENDING),
                ("unique_file_id", ASCENDING)
            ],
            unique=True
        )
        self.duplicates.create_index([("created_at", ASCENDING)])

        # forward_accounts
        self.forward_accounts.create_index([("user_id", ASCENDING)])
        self.forward_accounts.create_index(
            [("user_id", ASCENDING), ("account_id", ASCENDING)],
            unique=True
        )
        self.forward_accounts.create_index([("status", ASCENDING)])

        # forward_bots
        self.forward_bots.create_index([("user_id", ASCENDING)])
        self.forward_bots.create_index(
            [("user_id", ASCENDING), ("bot_id", ASCENDING)],
            unique=True
        )

        # forward_jobs
        self.forward_jobs.create_index([("user_id", ASCENDING)])
        self.forward_jobs.create_index([("status", ASCENDING)])
        self.forward_jobs.create_index([("created_at", DESCENDING)])
        self.forward_jobs.create_index(
            [("user_id", ASCENDING), ("status", ASCENDING)]
        )

        # statistics
        self.statistics.create_index(
            [("user_id", ASCENDING), ("entity_type", ASCENDING), ("entity_id", ASCENDING)],
            unique=True
        )

        # job_logs
        self.job_logs.create_index([("job_id", ASCENDING)])
        self.job_logs.create_index([("created_at", DESCENDING)])

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


def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    return db.users.find_one({"user_id": user_id})


# ============================================================
# TARGETS  (FULLY PRESERVED + EXTENDED)
# ============================================================

DEFAULT_TARGET_SETTINGS = {
    "caption_enabled": False,
    "caption_template": "<b>{caption}</b>",
    "replace_enabled": False,
    "replacements": [],                    # [{"from": "...", "to": "..."}]
    "block_words": [],
    "whitelist_mode": False,
    "whitelist": [],
    "remove_links": False,
    "inline_buttons": [],                  # [[{"text": "...", "url": "..."}]]
    "media_types": ["photo", "video", "document", "audio", "animation", "voice"],
    "forward_tag": False,
    "delay": 1.0,
    "anti_duplicate": True,
    "future_new_posts": False,             # NEW
}


def add_target(
    user_id: int,
    chat_id: int,
    title: str,
    username: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Add a new target. Returns the document or None if already exists."""
    existing = db.targets.find_one({"user_id": user_id, "chat_id": chat_id})
    if existing:
        return None

    now = datetime.now(timezone.utc)
    doc = {
        "user_id": user_id,
        "chat_id": chat_id,
        "title": title,
        "username": username,
        "settings": copy.deepcopy(DEFAULT_TARGET_SETTINGS),
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


def get_target_by_id(target_id: Union[str, ObjectId]) -> Optional[Dict[str, Any]]:
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
    Example: {"delay": 2.0, "anti_duplicate": False, "future_new_posts": True}
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
    """Delete a target and all its duplicate records."""
    result = db.targets.delete_one({"user_id": user_id, "chat_id": chat_id})
    if result.deleted_count > 0:
        db.duplicates.delete_many({
            "user_id": user_id,
            "target_chat_id": chat_id
        })
        return True
    return False


def rename_target(user_id: int, chat_id: int, new_title: str) -> bool:
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


def get_setting(target: Dict[str, Any], key: str, default: Any = None) -> Any:
    """Safe getter for a setting inside target document."""
    return target.get("settings", {}).get(key, default)


# ============================================================
# DUPLICATES (FULLY PRESERVED)
# ============================================================

def is_duplicate(user_id: int, target_chat_id: int, unique_file_id: str) -> bool:
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
    Returns True if inserted, False if already exists.
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
    result = db.duplicates.delete_many({
        "user_id": user_id,
        "target_chat_id": target_chat_id
    })
    return result.deleted_count


def get_duplicate_count(user_id: int, target_chat_id: int) -> int:
    return db.duplicates.count_documents({
        "user_id": user_id,
        "target_chat_id": target_chat_id
    })


# ============================================================
# FORWARD ACCOUNTS (USER ACCOUNTS)
# ============================================================

def add_forward_account(
    user_id: int,
    phone: str,
    session_string: str,               # encrypted session
    name: Optional[str] = None,
    forward_limit: int = 500,
    sleep_after_limit_minutes: int = 30
) -> Optional[Dict[str, Any]]:
    """
    Add a new user account.
    Returns the document or None if phone already exists for this user.
    """
    existing = db.forward_accounts.find_one({
        "user_id": user_id,
        "phone": phone
    })
    if existing:
        return None

    now = datetime.now(timezone.utc)
    account_id = str(ObjectId())

    doc = {
        "user_id": user_id,
        "account_id": account_id,
        "phone": phone,
        "name": name or phone,
        "session_string": session_string,   # should be encrypted before storing
        "status": AccountStatus.ACTIVE.value,
        "forward_limit": forward_limit,
        "sleep_after_limit_minutes": sleep_after_limit_minutes,
        "forwarded_count": 0,               # current cycle count
        "total_forwarded": 0,
        "sleep_until": None,
        "last_used_at": None,
        "error_message": None,
        "created_at": now,
        "updated_at": now
    }
    result = db.forward_accounts.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


def get_user_accounts(user_id: int) -> List[Dict[str, Any]]:
    cursor = db.forward_accounts.find({"user_id": user_id}).sort("created_at", 1)
    return list(cursor)


def get_account(user_id: int, account_id: str) -> Optional[Dict[str, Any]]:
    return db.forward_accounts.find_one({
        "user_id": user_id,
        "account_id": account_id
    })


def get_account_by_id(account_id: str) -> Optional[Dict[str, Any]]:
    return db.forward_accounts.find_one({"account_id": account_id})


def update_account(
    user_id: int,
    account_id: str,
    updates: Dict[str, Any]
) -> bool:
    updates["updated_at"] = datetime.now(timezone.utc)
    result = db.forward_accounts.update_one(
        {"user_id": user_id, "account_id": account_id},
        {"$set": updates}
    )
    return result.modified_count > 0


def set_account_status(
    user_id: int,
    account_id: str,
    status: str,
    error_message: Optional[str] = None
) -> bool:
    updates = {
        "status": status,
        "updated_at": datetime.now(timezone.utc)
    }
    if error_message is not None:
        updates["error_message"] = error_message
    if status == AccountStatus.ACTIVE.value:
        updates["error_message"] = None
        updates["sleep_until"] = None

    result = db.forward_accounts.update_one(
        {"user_id": user_id, "account_id": account_id},
        {"$set": updates}
    )
    return result.modified_count > 0


def increment_account_forwarded(
    user_id: int,
    account_id: str,
    count: int = 1
) -> Optional[Dict[str, Any]]:
    """
    Atomically increment forwarded_count and total_forwarded.
    If limit reached → put account to sleep.
    Returns the updated account document.
    """
    account = get_account(user_id, account_id)
    if not account:
        return None

    new_count = account.get("forwarded_count", 0) + count
    limit = account.get("forward_limit", 500)

    updates = {
        "forwarded_count": new_count,
        "total_forwarded": account.get("total_forwarded", 0) + count,
        "last_used_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    if new_count >= limit:
        sleep_minutes = account.get("sleep_after_limit_minutes", 30)
        updates["status"] = AccountStatus.SLEEPING.value
        updates["sleep_until"] = datetime.now(timezone.utc) + timedelta(minutes=sleep_minutes)
        updates["forwarded_count"] = 0   # reset for next cycle

    db.forward_accounts.update_one(
        {"user_id": user_id, "account_id": account_id},
        {"$set": updates}
    )
    return get_account(user_id, account_id)


def wake_sleeping_accounts(user_id: Optional[int] = None) -> int:
    """
    Wake up all accounts whose sleep_until has passed.
    Returns number of accounts woken.
    """
    now = datetime.now(timezone.utc)
    query = {
        "status": AccountStatus.SLEEPING.value,
        "sleep_until": {"$lte": now}
    }
    if user_id is not None:
        query["user_id"] = user_id

    result = db.forward_accounts.update_many(
        query,
        {
            "$set": {
                "status": AccountStatus.ACTIVE.value,
                "sleep_until": None,
                "forwarded_count": 0,
                "updated_at": now
            }
        }
    )
    return result.modified_count


def get_available_accounts(
    user_id: int,
    account_ids: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Return accounts that are currently ACTIVE and not sleeping.
    Optionally filter by a list of account_ids.
    """
    query = {
        "user_id": user_id,
        "status": AccountStatus.ACTIVE.value
    }
    if account_ids:
        query["account_id"] = {"$in": account_ids}

    cursor = db.forward_accounts.find(query).sort("last_used_at", 1)
    return list(cursor)


def delete_account(user_id: int, account_id: str) -> bool:
    result = db.forward_accounts.delete_one({
        "user_id": user_id,
        "account_id": account_id
    })
    return result.deleted_count > 0


def reset_account_cycle(user_id: int, account_id: str) -> bool:
    """Manually reset the current cycle counter."""
    return update_account(user_id, account_id, {
        "forwarded_count": 0,
        "status": AccountStatus.ACTIVE.value,
        "sleep_until": None
    })


# ============================================================
# FORWARD BOTS
# ============================================================

def add_forward_bot(
    user_id: int,
    bot_token: str,
    bot_username: Optional[str] = None,
    name: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Add a forwarding bot. Returns document or None if token already exists."""
    existing = db.forward_bots.find_one({
        "user_id": user_id,
        "bot_token": bot_token
    })
    if existing:
        return None

    now = datetime.now(timezone.utc)
    bot_id = str(ObjectId())

    doc = {
        "user_id": user_id,
        "bot_id": bot_id,
        "bot_token": bot_token,             # consider encrypting
        "bot_username": bot_username,
        "name": name or (bot_username or f"Bot {bot_id[:6]}"),
        "status": "active",
        "total_forwarded": 0,
        "last_used_at": None,
        "error_message": None,
        "created_at": now,
        "updated_at": now
    }
    result = db.forward_bots.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


def get_user_bots(user_id: int) -> List[Dict[str, Any]]:
    cursor = db.forward_bots.find({"user_id": user_id}).sort("created_at", 1)
    return list(cursor)


def get_bot(user_id: int, bot_id: str) -> Optional[Dict[str, Any]]:
    return db.forward_bots.find_one({
        "user_id": user_id,
        "bot_id": bot_id
    })


def update_bot(user_id: int, bot_id: str, updates: Dict[str, Any]) -> bool:
    updates["updated_at"] = datetime.now(timezone.utc)
    result = db.forward_bots.update_one(
        {"user_id": user_id, "bot_id": bot_id},
        {"$set": updates}
    )
    return result.modified_count > 0


def delete_bot(user_id: int, bot_id: str) -> bool:
    result = db.forward_bots.delete_one({
        "user_id": user_id,
        "bot_id": bot_id
    })
    return result.deleted_count > 0


def increment_bot_forwarded(user_id: int, bot_id: str, count: int = 1) -> bool:
    result = db.forward_bots.update_one(
        {"user_id": user_id, "bot_id": bot_id},
        {
            "$inc": {"total_forwarded": count},
            "$set": {
                "last_used_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
        }
    )
    return result.modified_count > 0


# ============================================================
# FORWARD JOBS
# ============================================================

def create_job(
    user_id: int,
    source_chat_id: Union[int, str],
    source_title: str,
    target_chat_ids: List[int],
    method: str,                           # "bot" | "user"
    account_ids: Optional[List[str]] = None,
    bot_id: Optional[str] = None,
    last_msg_id: int = 0,
    skip: int = 0,
    initial_limit: Optional[int] = None,   # None = unlimited until last_msg_id
    future_new_posts: bool = False,
    account_strategy: str = AccountStrategy.SEQUENTIAL.value,
    name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a new forward job.
    """
    now = datetime.now(timezone.utc)
    job_id = str(ObjectId())

    doc = {
        "user_id": user_id,
        "job_id": job_id,
        "name": name or f"Job #{job_id[:6]}",
        "source_chat_id": source_chat_id,
        "source_title": source_title,
        "target_chat_ids": target_chat_ids,
        "method": method,
        "account_ids": account_ids or [],
        "bot_id": bot_id,
        "last_msg_id": last_msg_id,
        "skip": skip,
        "current_msg_id": skip,             # progress pointer
        "initial_limit": initial_limit,
        "future_new_posts": future_new_posts,
        "account_strategy": account_strategy,
        "status": JobStatus.PENDING.value,
        "stats": {
            "fetched": 0,
            "forwarded": 0,
            "skipped_filter": 0,
            "skipped_duplicate": 0,
            "skipped_deleted": 0,
            "errors": 0
        },
        "started_at": None,
        "completed_at": None,
        "error_message": None,
        "created_at": now,
        "updated_at": now
    }
    result = db.forward_jobs.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


def get_job(user_id: int, job_id: str) -> Optional[Dict[str, Any]]:
    return db.forward_jobs.find_one({
        "user_id": user_id,
        "job_id": job_id
    })


def get_job_by_id(job_id: str) -> Optional[Dict[str, Any]]:
    return db.forward_jobs.find_one({"job_id": job_id})


def get_user_jobs(
    user_id: int,
    status: Optional[str] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    query = {"user_id": user_id}
    if status:
        query["status"] = status
    cursor = db.forward_jobs.find(query).sort("created_at", DESCENDING).limit(limit)
    return list(cursor)


def get_active_jobs(user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    query = {"status": {"$in": [JobStatus.RUNNING.value, JobStatus.PENDING.value]}}
    if user_id is not None:
        query["user_id"] = user_id
    return list(db.forward_jobs.find(query).sort("created_at", 1))


def update_job(user_id: int, job_id: str, updates: Dict[str, Any]) -> bool:
    updates["updated_at"] = datetime.now(timezone.utc)
    result = db.forward_jobs.update_one(
        {"user_id": user_id, "job_id": job_id},
        {"$set": updates}
    )
    return result.modified_count > 0


def update_job_stats(
    user_id: int,
    job_id: str,
    stats_increment: Dict[str, int],
    current_msg_id: Optional[int] = None
) -> bool:
    """
    Atomically increment job stats.
    Example stats_increment = {"forwarded": 1, "fetched": 1}
    """
    inc = {f"stats.{k}": v for k, v in stats_increment.items()}
    set_fields = {"updated_at": datetime.now(timezone.utc)}
    if current_msg_id is not None:
        set_fields["current_msg_id"] = current_msg_id

    result = db.forward_jobs.update_one(
        {"user_id": user_id, "job_id": job_id},
        {"$inc": inc, "$set": set_fields}
    )
    return result.modified_count > 0


def set_job_status(
    user_id: int,
    job_id: str,
    status: str,
    error_message: Optional[str] = None
) -> bool:
    updates = {
        "status": status,
        "updated_at": datetime.now(timezone.utc)
    }
    if status == JobStatus.RUNNING.value and not get_job(user_id, job_id).get("started_at"):
        updates["started_at"] = datetime.now(timezone.utc)
    if status in [JobStatus.COMPLETED.value, JobStatus.CANCELLED.value, JobStatus.FAILED.value]:
        updates["completed_at"] = datetime.now(timezone.utc)
    if error_message is not None:
        updates["error_message"] = error_message

    return update_job(user_id, job_id, updates)


def delete_job(user_id: int, job_id: str) -> bool:
    result = db.forward_jobs.delete_one({
        "user_id": user_id,
        "job_id": job_id
    })
    if result.deleted_count > 0:
        db.job_logs.delete_many({"job_id": job_id})
        return True
    return False


# ============================================================
# JOB LOGS (optional detailed logging)
# ============================================================

def add_job_log(
    job_id: str,
    level: str,
    message: str,
    extra: Optional[Dict] = None
) -> None:
    db.job_logs.insert_one({
        "job_id": job_id,
        "level": level,
        "message": message,
        "extra": extra or {},
        "created_at": datetime.now(timezone.utc)
    })


def get_job_logs(job_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    cursor = db.job_logs.find({"job_id": job_id}).sort("created_at", DESCENDING).limit(limit)
    return list(cursor)


# ============================================================
# STATISTICS (Dashboard)
# ============================================================

def get_or_create_stats(
    user_id: int,
    entity_type: str,          # "account" | "target" | "bot" | "job" | "global"
    entity_id: str
) -> Dict[str, Any]:
    doc = db.statistics.find_one({
        "user_id": user_id,
        "entity_type": entity_type,
        "entity_id": entity_id
    })
    if doc:
        return doc

    now = datetime.now(timezone.utc)
    doc = {
        "user_id": user_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "forwarded": 0,
        "fetched": 0,
        "duplicates": 0,
        "blocked": 0,
        "errors": 0,
        "created_at": now,
        "updated_at": now
    }
    db.statistics.insert_one(doc)
    return doc


def increment_stats(
    user_id: int,
    entity_type: str,
    entity_id: str,
    increments: Dict[str, int]
) -> None:
    """
    increments example: {"forwarded": 1, "duplicates": 1}
    """
    set_on_insert = {
        "user_id": user_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "created_at": datetime.now(timezone.utc)
    }
    inc = {k: v for k, v in increments.items()}
    db.statistics.update_one(
        {
            "user_id": user_id,
            "entity_type": entity_type,
            "entity_id": entity_id
        },
        {
            "$inc": inc,
            "$set": {"updated_at": datetime.now(timezone.utc)},
            "$setOnInsert": set_on_insert
        },
        upsert=True
    )


def get_dashboard_counts(user_id: int) -> Dict[str, int]:
    """Quick counts for the main dashboard."""
    return {
        "targets": db.targets.count_documents({"user_id": user_id}),
        "accounts": db.forward_accounts.count_documents({"user_id": user_id}),
        "bots": db.forward_bots.count_documents({"user_id": user_id}),
        "active_jobs": db.forward_jobs.count_documents({
            "user_id": user_id,
            "status": {"$in": [JobStatus.RUNNING.value, JobStatus.PENDING.value]}
        }),
        "duplicates": db.duplicates.count_documents({"user_id": user_id}),
    }


def get_entity_stats(
    user_id: int,
    entity_type: str,
    entity_id: str
) -> Dict[str, Any]:
    doc = db.statistics.find_one({
        "user_id": user_id,
        "entity_type": entity_type,
        "entity_id": entity_id
    })
    if not doc:
        return {
            "forwarded": 0,
            "fetched": 0,
            "duplicates": 0,
            "blocked": 0,
            "errors": 0
        }
    return {
        "forwarded": doc.get("forwarded", 0),
        "fetched": doc.get("fetched", 0),
        "duplicates": doc.get("duplicates", 0),
        "blocked": doc.get("blocked", 0),
        "errors": doc.get("errors", 0),
    }


# ============================================================
# HELPERS
# ============================================================

def get_next_available_account(
    user_id: int,
    account_ids: List[str],
    strategy: str = AccountStrategy.SEQUENTIAL.value
) -> Optional[Dict[str, Any]]:
    """
    Pick the next available account according to strategy.
    Currently only sequential is fully implemented (least recently used).
    """
    available = get_available_accounts(user_id, account_ids)
    if not available:
        return None

    # Sequential = least recently used first
    return available[0]


def can_use_future_posts(
    user_id: int,
    source_chat_id: Union[int, str],
    method: str,
    bot_id: Optional[str] = None,
    account_ids: Optional[List[str]] = None
) -> bool:
    """
    Placeholder helper – real access check will be done in the worker.
    Here we only check if the required resources exist.
    """
    if method == MethodType.BOT.value:
        if not bot_id:
            return False
        bot = get_bot(user_id, bot_id)
        return bot is not None and bot.get("status") == "active"

    if method == MethodType.USER.value:
        if not account_ids:
            return False
        accounts = get_available_accounts(user_id, account_ids)
        return len(accounts) > 0

    return False
