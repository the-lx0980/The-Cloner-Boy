import os
import datetime
import logging
import time
import requests
import urllib3
from tmdbv3api import TMDb, TV, Season
from .database import get_series_year, save_series_year

logger = logging.getLogger("AIYearFetcher")

# Load TMDB key from environment
TMDB_API_KEY = "b043bef236e1b972f25dcb382ef1af76"


def get_season_release_year_robust(series_name, season_number, retries=5):
    tmdb = TMDb()
    tmdb.api_key = TMDB_API_KEY
    tmdb.language = "en"

    tv = TV()
    season = Season()

    for attempt in range(1, retries + 1):
        try:
            search_results = tv.search(series_name)
            if not search_results:
                logger.error(f"❌ No search results for '{series_name}'.")
                return None

            series_id = search_results[0].id
            season_details = season.details(series_id, season_number)
            # Handle dict or object
            air_date = getattr(season_details, "air_date", None) if not isinstance(season_details, dict) else season_details.get("air_date")

            if air_date:
                year = int(datetime.datetime.strptime(air_date, "%Y-%m-%d").year)
                logger.info(f"✅ {series_name} S{season_number}: {year}")
                return year
            else:
                logger.warning(f"ℹ️ No air date for '{series_name}' Season {season_number}.")
                return None

        except (requests.exceptions.ConnectionError,
                urllib3.exceptions.ProtocolError,
                ConnectionResetError) as e:
            logger.warning(f"⚠️ Network error (attempt {attempt}/{retries}) for '{series_name}' S{season_number}: {e}")
            time.sleep(2 ** attempt)  # exponential backoff
            continue

        except Exception as e:
            if "could not be found" in str(e).lower():
                break
            logger.error(f"⚠️ Error fetching '{series_name}' season {season_number}: {e}")
            return None

    logger.error(f"❌ No valid data found for '{series_name}' season {season_number}.")
    return None


# ---------------------------
# Async wrapper to check DB first
# ---------------------------
async def get_or_fetch_series_year(title: str, season: int) -> int | None:
    """
    1️⃣ Check MongoDB first.
    2️⃣ If missing, fetch from TMDb robust function.
    3️⃣ Save automatically in DB.
    """
    # 1️⃣ Check DB
    year = get_series_year(title, season)
    if year:
        logger.info(f"📦 Found in DB: {title} S{season} → {year}")
        return year

    # 2️⃣ Fetch from TMDb
    logger.info(f"🔍 Year missing for {title} S{season}, fetching from TMDb...")
    year = get_season_release_year_robust(title, season)
    if year:
        # 3️⃣ Save to DB
        save_series_year(title, season, year)
    return year
