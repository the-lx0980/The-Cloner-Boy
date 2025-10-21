import logging
import asyncio
from .database import get_movie_year, save_movie_year
import tmdbsimple as tmdb

logger = logging.getLogger("MovieYearFetcher")

# Set your TMDb API key
tmdb.API_KEY = "YOUR_TMDB_API_KEY"


def fetch_movie_year_tmdb(title: str) -> int | None:
    """
    Fetch movie release year from TMDb using movie title.
    """
    try:
        search = tmdb.Search()
        response = search.movie(query=title)
        results = response.get("results", [])

        if not results:
            logger.warning(f"⚠️ TMDb: No results found for '{title}'")
            return None

        # Take the first result
        movie_data = results[0]
        year = None
        release_date = movie_data.get("release_date")  # format: 'YYYY-MM-DD'
        if release_date and len(release_date) >= 4:
            year = int(release_date[:4])

        if year:
            save_movie_year(title, year)
            logger.info(f"✅ TMDb: Saved {title} → {year}")
            return year

        return None

    except Exception as e:
        logger.exception(f"❌ TMDb fetch failed for {title}: {e}")
        return None


async def get_or_fetch_movie_year(title: str) -> int | None:
    """
    Async version:
    1. Check MongoDB first.
    2. If missing, fetch from TMDb asynchronously.
    3. Store in MongoDB.
    """
    # 1️⃣ Check DB
    year = get_movie_year(title)
    if year:
        logger.info(f"📦 Found in DB: {title} → {year}")
        return year

    # 2️⃣ Fetch from TMDb
    logger.info(f"🔍 Year missing for '{title}', fetching via TMDb asynchronously...")
    try:
        year = fetch_movie_year_tmdb_async(title)
    except Exception as e:
        logger.error(f"❌ TMDb fetch failed for '{title}': {e}")
        return None

    if year:
        save_movie_year(title, year)
        logger.info(f"✅ Saved movie year: {title} → {year}")
    else:
        logger.warning(f"⚠️ Could not fetch year for '{title}' from TMDb")

    return year
