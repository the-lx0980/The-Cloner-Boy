
import os, asyncio
from itertools import cycle
from openai import OpenAI
from pyrogram import enums
from pyrogram.errors import FloodWait


keys = os.environ.get("OPENAI_API_KEYS")
if not keys:
    raise Exception("No OpenAI API keys found. Set OPENAI_API_KEYS in environment.")

OPENAI_API_KEYS = [k.strip() for k in keys.split(",") if k.strip()]
if not OPENAI_API_KEYS:
    raise Exception("No valid API keys found in OPENAI_API_KEYS.")

# Round-robin cycle for sequential rotation
_ai_key_cycle = cycle(OPENAI_API_KEYS)

def get_ai_client() -> OpenAI:
    """
    Returns an OpenAI client with the next API key in the cycle.
    """
    key = next(_ai_key_cycle)
    # Optional: print(f"🔑 Using OpenAI Key: {key[:8]}...")
    return OpenAI(api_key=key)


# ───────────────────────────────
# AI CAPTION EXTRACTION
# ───────────────────────────────
async def extract_caption_ai(caption: str) -> str:
    """
    Send caption to OpenAI to clean & format for movie/series.
    Returns formatted caption or original if AI fails.
    """
    ai = get_ai_client()
    prompt = f"""
You are a highly accurate movie and series caption formatter.

Your task:
1. Detect whether the caption is a movie or a series.
2. Reformat details properly.

Movies format:
<Movie Name> (<Year>) <Quality> <Print> <Audio>

Series format:
<Series Name> (<Year>) S<SeasonNo:02d> [E<EpisodeNo:02d> or E<EpisodeRange>] <Quality> <Print> <Audio>

Rules:
- Season: S01, S02...
- Episode: E01, E02...
- Episode ranges: E01–E10
- "Complete" after season if applicable
- Audio: Dual Audio / Multi Audio formatting
- Include print info (DDP 5.1, ORG) if present
- No Markdown or emojis
- Keep spacing clean
- Skip missing/unknown fields

Input caption:
{caption}

Return only the cleaned formatted caption.
"""
    try:
        response = ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("AI Error:", e)
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
                    caption=f"***{caption or ''}***"
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
                caption=f'***{message.caption or ""}***',
                parse_mode=enums.ParseMode.MARKDOWN
            )
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await forwards_messages(bot, message, from_chat, to_chat, ai_caption)
