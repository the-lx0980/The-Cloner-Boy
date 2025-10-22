import os
import datetime
import logging
from tmdbv3api import TMDb, TV, Season
from .database import get_series_year, save_series_year

logger = logging.getLogger("AIYearFetcher")

# Load TMDB key from environment
TMDB_API_KEY = ""


def fetch_series_year_tmdb(series_name: str, season_number: int) -> int | None:
    """
    Fetch release year of a specific TV season from TMDb.
    """
    if not TMDB_API_KEY:
        logger.error("❌ TMDB_API_KEY not set in environment!")
        return None

    tmdb = TMDb()
    tmdb.api_key = TMDB_API_KEY
    tmdb.language = "en"

    tv = TV()
    season = Season()

    try:
        # 1️⃣ Search for the TV series
        results = tv.search(series_name)
        if not results:
            logger.warning(f"❌ Series '{series_name}' not found on TMDb.")
            return None

        series_id = results[0].id

        # 2️⃣ Fetch season details
        season_data = season.details(series_id, season_number)
        air_date = getattr(season_data, "air_date", None)

        # 3️⃣ Extract year
        if air_date:
            try:
                year = datetime.datetime.strptime(air_date, "%Y-%m-%d").year
                logger.info(f"✅ {series_name} Season {season_number}: {year}")
                save_series_year(series_name, season_number, year)
                return year
            except ValueError:
                logger.warning(f"⚠️ Invalid air_date format: {air_date}")
        else:
            logger.warning(f"ℹ️ No air date found for {series_name} S{season_number}")
        return None

    except Exception as e:
        logger.error(f"⚠️ Error fetching '{series_name}' S{season_number}: {e}")
        return None


async def get_or_fetch_series_year(title: str, season: int) -> int | None:
    """
    1️⃣ Check MongoDB first.
    2️⃣ If missing, fetch from TMDb.
    3️⃣ Save automatically.
    """
    year = get_series_year(title, season)
    if year:
        logger.info(f"📦 Found in DB: {title} S{season} → {year}")
        return year

    logger.info(f"🔍 Year missing for {title} S{season}, fetching from TMDb...")
    return fetch_series_year_tmdb(title, season)
