import random
import datetime
import logging
from tmdbv3api import TMDb, TV, Season
import requests
import asyncio
from .database import get_series_year, save_series_year
from utils.tmdb_utils import tmdbapi
logger = logging.getLogger("AIYearFetcher")

TMDB_API_KEY = random.choice(tmdbapi)

async def get_season_release_year_robust(series_name: str, season_number: int, api_key: str, retries: int = 3) -> int | None:
    tmdb = TMDb()
    tmdb.api_key = api_key
    tmdb.language = "en"
    
    tv = TV()
    season = Season()

    await asyncio.sleep(5)
    for attempt in range(1, retries + 1):
        try:
            search_results = tv.search(series_name)
            if not search_results:
                logger.warning(f"🔎 No TMDb results for '{series_name}' (attempt {attempt}/{retries})")
                await asyncio.sleep(5)
                continue

            series_id = search_results[0].id
            season_details = season.details(series_id, season_number)
            air_date = getattr(season_details, "air_date", None)

            if air_date:
                year = datetime.datetime.strptime(air_date, "%Y-%m-%d").year
                return year
            else:
                logger.info(f"ℹ️ No air date for '{series_name}' Season {season_number}")
                return None

        except requests.exceptions.ConnectionError as e:
            logger.warning(f"⚠️ Network error (attempt {attempt}/{retries}): {e}")
            await asyncio.sleep(5)

        except Exception as e:
            if "could not be found" in str(e).lower():
                logger.error(f"🚫 Series not found: {series_name} S{season_number}")
                break
            else:
                logger.error(f"⚠️ Error fetching '{series_name}' S{season_number}: {e}")
                return None

    logger.error(f"❌ No valid data found for '{series_name}' Season {season_number}")
    return None

async def get_or_fetch_series_year(title: str, season: int) -> int | None:
    """
    1️⃣ Check MongoDB first.
    2️⃣ If missing, fetch from TMDb robust function.
    3️⃣ Save automatically in DB.
    """
    year = get_series_year(title, int(season))
    if year:
        logger.info(f"📦 Found in DB: {title} S{season} → {year}")
        return year
        
    logger.info(f"🔍 Year missing for {title} S{season}, fetching from TMDb...")
    year = await get_season_release_year_robust(title, season, TMDB_API_KEY)
    
    if isinstance(year, int):
        save_series_year(title, season, year)
        logger.info(f"💾 Saved to DB: {title} S{season} → {year}")
        return year
    
    return None
