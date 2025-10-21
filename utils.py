import time
import asyncio
import logging
import os
from itertools import cycle
from openai import OpenAI
import openai
from pyrogram.errors import FloodWait
from pyrogram import enums

logger = logging.getLogger(__name__)

# Load API keys
keys = os.environ.get("OPENAI_API_KEYS")
if not keys:
    raise Exception("No OpenAI API keys found in environment.")

OPENAI_API_KEYS = [k.strip() for k in keys.split(",") if k.strip()]
if not OPENAI_API_KEYS:
    raise Exception("No valid API keys found.")

# Round-robin client cycle
_clients = [OpenAI(api_key=k) for k in OPENAI_API_KEYS]
_client_cycle = cycle(_clients)

# Per-key cooldown tracker
_key_cooldowns = {c.api_key: 0 for c in _clients}

# Async lock (to avoid concurrent rotation issues)
_ai_lock = asyncio.Lock()

# Model fallback priority
MODEL_PRIORITY = ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"]


def _next_client() -> OpenAI:
    """Return next available client skipping cooldown keys."""
    now = time.time()
    for _ in range(len(_clients)):
        client = next(_client_cycle)
        if now >= _key_cooldowns[client.api_key]:
            return client
    logger.warning("⚠️ All API keys on cooldown, waiting 30s...")
    time.sleep(30)
    return next(_client_cycle)


async def get_ai_client() -> OpenAI:
    """Thread-safe client getter."""
    async with _ai_lock:
        return _next_client()


async def extract_caption_ai(caption: str) -> str:
    """Format movie/series captions using OpenAI with auto key & model rotation."""
    if not caption or len(caption.strip()) < 3:
        logger.debug("🟡 Skipped empty caption.")
        return caption

    prompt = f"""
You are a professional movie/series caption formatter.
Format cleanly without emojis or extra punctuation.

Input:
{caption}
"""

    model_index = 0  # Start with the highest priority model

    for attempt in range(6):
        client = await get_ai_client()
        model = MODEL_PRIORITY[model_index]
        try:
            logger.info(f"🧠 Sending to {model} (attempt {attempt + 1})")

            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                timeout=20,
            )
            formatted = response.choices[0].message.content.strip()
            logger.info(f"✅ Caption formatted with {model}.")
            return formatted

        except openai.RateLimitError as e:
            msg = getattr(e, "message", str(e))
            logger.warning(f"🚫 Rate limit: {msg}. Cooling down key...")
            _key_cooldowns[client.api_key] = time.time() + 120
            await asyncio.sleep(1)

        except openai.AuthenticationError:
            logger.error("❌ Invalid key — disabling for 10 minutes.")
            _key_cooldowns[client.api_key] = time.time() + 600

        except openai.APIConnectionError:
            logger.warning("🌐 Connection error. Retrying in 3s...")
            await asyncio.sleep(3)

        except openai.InternalServerError:
            logger.warning("🧩 Internal server error. Retrying in 3s...")
            await asyncio.sleep(3)

        except Exception as e:
            logger.exception(f"❌ Unexpected AI error: {e}")
            await asyncio.sleep(2)

        # If repeated errors, fallback model
        if attempt in (2, 4) and model_index + 1 < len(MODEL_PRIORITY):
            model_index += 1
            logger.warning(f"🔁 Switching fallback model → {MODEL_PRIORITY[model_index]}")

    logger.warning("⚠️ All models/keys failed. Returning original caption.")
    return caption

async def forwards_messages(bot, message, from_chat, to_chat, ai_caption):
    if message.media: 
        media_type = message.media.value
        media = getattr(message, media_type, None)
        if media:
            if message.caption:
                caption = message.caption
            elif message.video:
                caption = message.video.file_name
            elif message.document:
                caption = message.document.file_name
            elif message.audio:
                caption = message.audio.file_name 
            else:
                caption = None

            if ai_caption and caption:
                caption = await extract_caption_ai(caption)

            try:
                await bot.send_cached_media(
                    chat_id=to_chat,
                    file_id=media.file_id,
                    caption=f"**{caption or ''}**"
                )
            except FloodWait as e:
                await asyncio.sleep(e.value)
                await forwards_messages(bot, message, from_chat, to_chat, ai_caption)
    else:
        try:
            await bot.copy_message(
                chat_id=to_chat,
                from_chat_id=from_chat,
                message_id=message.id,
                caption=f'**{message.caption or ""}**',
                parse_mode=enums.ParseMode.MARKDOWN
            )
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await forwards_messages(bot, message, from_chat, to_chat, ai_caption)
