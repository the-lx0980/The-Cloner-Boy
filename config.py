# config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # ==================== TELEGRAM ====================
    API_ID = int(os.getenv("API_ID", 0))
    API_HASH = os.getenv("API_HASH", "")
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")          # Management Bot Token

    # ==================== MONGODB ====================
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    DB_NAME = os.getenv("DB_NAME", "forward_bot")

    # ==================== ADMINS ====================
    # Comma separated user IDs
    ADMINS = [int(x) for x in os.getenv("ADMINS", "").split(",") if x.strip().isdigit()]

    # ==================== DEFAULT TARGET SETTINGS ====================
    DEFAULT_SETTINGS = {
        "caption_enabled": False,
        "caption_template": "<b>{caption}</b>",
        "replace_enabled": False,
        "replacements": [],
        "block_words": [],
        "whitelist_mode": False,
        "whitelist": [],
        "remove_links": False,
        "inline_buttons": [],
        "media_types": ["photo", "video", "document", "audio", "animation", "voice"],
        "forward_tag": False,
        "delay": 1.0,
        "anti_duplicate": True,
        "future_new_posts": False,
    }

    # ==================== ACCOUNT DEFAULTS ====================
    DEFAULT_FORWARD_LIMIT = 500
    DEFAULT_SLEEP_MINUTES = 30

    # ==================== JOB DEFAULTS ====================
    DEFAULT_ACCOUNT_STRATEGY = "sequential"   # sequential | manual