import os
import asyncio
import logging
from itertools import cycle
import openai
from pyrogram.errors import FloodWait
from pyrogram import enums

logging.basicConfig(
    format="%(asctime)s - [AI-CAPTION] - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("AICaptionExtractor")

keys = os.environ.get("OPENAI_API_KEYS") or os.environ.get("OPENAI_API_KEY")

if not keys:
    raise Exception("❌ No OpenAI API keys found. Set OPENAI_API_KEYS or OPENAI_API_KEY in environment.")

OPENAI_API_KEYS = [k.strip() for k in keys.split(",") if k.strip()]
if not OPENAI_API_KEYS:
    raise Exception("❌ No valid API keys found.")

if len(OPENAI_API_KEYS) == 1:
    _ai_client = openai.OpenAI(api_key=OPENAI_API_KEYS[0])

    def get_ai_client() -> openai.OpenAI:
        """Return the single pre-initialized OpenAI client."""
        return _ai_client
    logger.info("🔑 Single API key mode enabled.")
else:
    _ai_clients = [openai.OpenAI(api_key=k) for k in OPENAI_API_KEYS]
    _client_cycle = cycle(_ai_clients)

    def get_ai_client() -> openai.OpenAI:
        """Return the next OpenAI client (round-robin rotation)."""
        return next(_client_cycle)
    logger.info(f"🔁 Multi-key rotation enabled ({len(OPENAI_API_KEYS)} keys).")

async def extract_caption_ai(caption: str) -> str:
    """
    Clean and format captions for movies or series using OpenAI.
    Returns the formatted caption or original caption if AI fails.
    """
    if not caption or len(caption.strip()) < 3:
        logger.debug("🟡 Skipped empty/short caption for AI processing.")
        return caption

    ai = get_ai_client()
    prompt = f"""
You are a highly accurate movie and series caption formatter.

Rules:
- Detect movie/series.
- Format neatly, no emojis.
- Return only text.

Input caption:
{caption}
"""

    for attempt in range(3):
        try:
            logger.info(f"🧠 Sending caption to AI (attempt {attempt + 1})")
            response = ai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                timeout=20,
            )
            formatted = response.choices[0].message.content.strip()
            logger.info("✅ Caption formatted successfully.")
            return formatted

        except FloodWait as e:
            logger.warning(f"⚠️ FloodWait: sleeping {e.value}s before retry.")
            await asyncio.sleep(e.value)

        except openai.RateLimitError as e:
            logger.warning(f"🚫 Rate limit reached: {e.message}. Rotating key...")
            ai = get_ai_client()
            await asyncio.sleep(2)

        except openai.AuthenticationError as e:
            logger.error(f"❌ Invalid API key: {e.message}. Switching key.")
            ai = get_ai_client()

        except openai.PermissionDeniedError as e:
            logger.error(f"🚷 Permission denied: {e.message}. Rotating key.")
            ai = get_ai_client()

        except openai.APIConnectionError as e:
            logger.warning(f"🌐 Connection error: {e}. Retrying...")
            await asyncio.sleep(3)

        except openai.InternalServerError as e:
            logger.warning(f"🧩 Internal server error: {e.message}. Retrying...")
            await asyncio.sleep(3)

        except openai.ServiceUnavailableError as e:
            logger.warning(f"🕒 Service unavailable: {e.message}. Retrying...")
            await asyncio.sleep(3)

        except openai.BadRequestError as e:
            logger.error(f"⚠️ Bad request: {e.message}")
            break

        except Exception as e:
            logger.exception(f"❌ Unexpected AI Caption Error: {e}")
            await asyncio.sleep(2)

    logger.warning("⚠️ AI formatting failed after retries. Using original caption.")
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
