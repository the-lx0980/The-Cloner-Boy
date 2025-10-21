import os, asyncio
from itertools import cycle
from openai import OpenAI
from pyrogram import enums
from pyrogram.errors import FloodWait


keys = os.environ.get("OPENAI_API_KEYS") or os.environ.get("OPENAI_API_KEY")

if not keys:
    raise Exception("No OpenAI API keys found. Set OPENAI_API_KEYS or OPENAI_API_KEY in environment.")

# Split and clean
OPENAI_API_KEYS = [k.strip() for k in keys.split(",") if k.strip()]

if not OPENAI_API_KEYS:
    raise Exception("No valid API keys found.")

# If only one key → single client mode
if len(OPENAI_API_KEYS) == 1:
    _ai_client = OpenAI(api_key=OPENAI_API_KEYS[0])

    def get_ai_client() -> OpenAI:
        """Always return the same client (fast single-key mode)."""
        return _ai_client

else:
    # Multiple keys → pre-create clients and rotate sequentially
    _ai_clients = [OpenAI(api_key=k) for k in OPENAI_API_KEYS]
    _client_cycle = cycle(_ai_clients)

    def get_ai_client() -> OpenAI:
        """Return next client in round-robin (multi-key mode)."""
        return next(_client_cycle)
        


async def extract_caption_ai(caption: str) -> str:
    """
    Send caption to OpenAI to clean & format for movie/series.
    Returns formatted caption or original if AI fails.
    """
    ai = get_ai_client()
    prompt = f"""
You are a highly accurate movie and series caption formatter.

Your task:
1. Detect whether the caption refers to a **movie** or a **series**.
2. Extract and reformat details properly using the following rules.

────────────────────────────
🎬 FOR MOVIES:
Format:
<Movie Name> (<Year>) <Quality> <Print> <Audio>

Example:
Venom (2021) 1080p WEB-DL Dual Audio (Hindi + English)

────────────────────────────
📺 FOR SERIES:
Format:
<Series Name> (<Year>) S<SeasonNo:02d> [E<EpisodeNo:02d> or E<EpisodeRange>] <Quality> <Print> <Audio>

Examples:
Loki (2023) S01 E03 1080p WEB-DL Dual Audio (Hindi + English)
Squid Game (2025) S03 E01–E10 1080p DS4K DDP 5.1 Multi Audio (Hindi + English + Korean)
Peacemaker (2025) S02 Complete 480p HEVC Dual Audio (Hindi + English)

────────────────────────────
Formatting Rules:
- Season format: S01, S02, … (not “Season 1”)
- Episode format: E01, E02, … (not “Episode 1”)
- Episode range (e.g. “E01 - E10”) → “E01–E10”
- If “Complete” season is mentioned, include “Complete” after the season.
- Audio:
    - “[Hindi - English]” → “Dual Audio (Hindi + English)”
    - “[Hindi - English - Korean]” → “Multi Audio (Hindi + English + Korean)”
    - Include “DDP 5.1”, “ORG”, etc., after the print if present.
- Keep spacing clean and consistent.
- Skip unknown or missing fields gracefully (do not guess).
- Output plain text only (no Markdown, no emojis).

────────────────────────────
Input caption:
{caption}

Return only the cleaned and formatted caption.
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
