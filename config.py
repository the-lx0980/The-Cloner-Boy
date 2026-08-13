# config.py

import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    API_ID = int(os.getenv("API_ID", "0"))
    API_HASH = os.getenv("API_HASH", "")
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")

    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    DB_NAME = os.getenv("DB_NAME", "forward_bot")

    # Only these user IDs can use the bot
    ADMINS = [int(x) for x in os.getenv("ADMINS", "").split() if x.isdigit()]

    DEFAULT_SETTINGS = {
        "caption_enabled": False,
        "caption_template": "<b>{caption}</b>",
        "replace_enabled": False,
        "replacements": [],
        "block_words": [],
        "whitelist": [],
        "whitelist_mode": False,
        "remove_links": False,
        "inline_buttons": [],
        "media_types": ["photo", "video", "document", "audio", "sticker"],
        "forward_tag": False,
        "delay": 1.0,
        "anti_duplicate": True
    }
