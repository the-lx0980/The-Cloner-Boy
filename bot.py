import os
import sys

# Automatic root directory setup to fix 'No module named' errors
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import asyncio
import importlib
import logging
import time
from typing import AsyncGenerator, Optional, Union

from botlogger import LOGGER
from config import Config as config
from database import db
from handlers import ALL_MODULES  # Loaded correctly from handlers
from pyrogram import Client, idle, types

# ==================== LOGGING SETUP ====================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Reduce noise from third-party libraries
logging.getLogger("pyrogram").setLevel(logging.WARNING)
logging.getLogger("pymongo").setLevel(logging.WARNING)

# Uptime tracking
START_TIME = time.time()


# ==================== BOT CLASS DEFINITION ====================
class Bot(Client):
    """Custom Pyrogram Client with extended helper methods."""

    def __init__(self):
        super().__init__(
            name="ForwardBot",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            bot_token=config.BOT_TOKEN,
            max_concurrent_transmissions=7,
        )
        self.id: Optional[int] = None
        self.name: Optional[str] = None
        self.username: Optional[str] = None

    async def start(self, *args, **kwargs):
        """Starts the bot client and initializes database connection."""
        await super().start(*args, **kwargs)
        me = await self.get_me()
        self.id = me.id
        self.name = me.first_name
        self.username = me.username

        try:
            db.connect()
            logger.info("✅ MongoDB connected successfully")
        except Exception as e:
            logger.error(f"❌ MongoDB connection failed: {e}")
            raise

    async def stop(self, *args, **kwargs):
        """Safely stops the bot client."""
        await super().stop(*args, **kwargs)

    async def iter_messages(
        self, chat_id: Union[int, str], limit: int, offset: int = 0
    ) -> Optional[AsyncGenerator["types.Message", None]]:
        """Iterate through a chat sequentially.

        Fetches messages in chunks to save boilerplate code.
        """
        current = offset
        while True:
            new_diff = min(200, limit - current)
            if new_diff <= 0:
                return

            messages = await self.get_messages(
                chat_id, list(range(current, current + new_diff + 1))
            )
            for message in messages:
                yield message
                current += 1


# Initialize the bot client instance
app = Bot()


# ==================== BOOT & STARTUP LOGIC ====================
async def boot():
    """Bootstraps, loads handlers, and runs the Telegram bot."""
    LOGGER(__name__).info("Bot is starting...")
    await app.start()
    LOGGER(__name__).info("Bot started successfully.")

    # Dynamically load all handlers after app has started
    for module in ALL_MODULES:
        try:
            # FIXED: Changed from 'modules.' to 'handlers.'
            importlib.import_module(f"handlers.{module}")
            LOGGER(__name__).info(f"Successfully loaded handler: {module}")
        except Exception as e:
            LOGGER(__name__).error(f"Failed to load handler {module}: {e}")

    try:
        await idle()
    finally:
        LOGGER(__name__).warning("Bot is shutting down...")
        await app.stop()


if __name__ == "__main__":
    try:
        asyncio.get_event_loop().run_until_complete(boot())
    except KeyboardInterrupt:
        LOGGER(__name__).warning("Bot interrupted by user or system.")
