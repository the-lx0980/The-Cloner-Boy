import os
import re
import asyncio
import logging
from itertools import cycle
import openai

from .database import get_series_year, save_series_year

logger = logging.getLogger("AIYearFetcher")

# -------------------------------
# OpenAI Key Setup
# -------------------------------
keys = os.environ.get("OPENAI_API_KEYS") or os.environ.get("OPENAI_API_KEY")

if not keys:
    raise Exception("❌ No OpenAI API keys found. Please set OPENAI_API_KEYS or OPENAI_API_KEY.")

OPENAI_API_KEYS = [k.strip() for k in keys.split(",") if k.strip()]
if not OPENAI_API_KEYS:
    raise Exception("❌ No valid API keys provided.")

if len(OPENAI_API_KEYS) == 1:
    _ai_client = openai.OpenAI(api_key=OPENAI_API_KEYS[0])

    def get_ai_client() -> openai.OpenAI:
        return _ai_client
else:
    _ai_clients = [openai.OpenAI(api_key=k) for k in OPENAI_API_KEYS]
    _client_cycle = cycle(_ai_clients)

    def get_ai_client() -> openai.OpenAI:
        return next(_client_cycle)


# -------------------------------
# AI Fetch Function
# -------------------------------
async def fetch_series_year_ai(title: str, season: int) -> int | None:
    """
    Ask AI: "What is the release year of <series> Season <season>?"
    Returns 4-digit year or None.
    """
    ai = get_ai_client()
    prompt = f"""
You are a film and TV database expert.
Return ONLY the 4-digit release year of the given season.
If unknown, say "unknown".

Series Name: {title}
Season: {season}
"""

    for attempt in range(3):
        try:
            logger.info(f"🧠 Fetching year via AI → {title} S{season} (attempt {attempt + 1})")

            response = ai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                timeout=20,
            )

            answer = response.choices[0].message.content.strip()
            match = re.search(r"\b(19|20)\d{2}\b", answer)
            if match:
                year = int(match.group(0))
                save_series_year(title, season, year)
                logger.info(f"✅ AI found year: {title} S{season} → {year}")
                return year
            else:
                logger.warning(f"⚠️ AI could not detect year for {title} S{season}: {answer}")
                return None

        except openai.RateLimitError:
            logger.warning("🚫 Rate limit hit — rotating key...")
            ai = get_ai_client()
            await asyncio.sleep(2)

        except Exception as e:
            logger.exception(f"❌ AI fetch failed: {e}")
            await asyncio.sleep(2)

    return None


# -------------------------------
# Auto Wrapper (DB + AI)
# -------------------------------
async def get_or_fetch_series_year(title: str, season: int) -> int | None:
    """
    1. Check MongoDB first.
    2. If missing, ask AI.
    3. Store result automatically.
    """
    year = get_series_year(title, season)
    if year:
        logger.info(f"📦 Found in DB: {title} S{season} → {year}")
        return year

    logger.info(f"🔍 Year missing for {title} S{season}, fetching via AI...")
    return await fetch_series_year_ai(title, season)
