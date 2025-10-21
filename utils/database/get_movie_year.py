import logging
import asyncio
from .database import get_movie_year, save_movie_year
import tmdbsimple as tmdb
import re
from PTT import parse_title

logger = logging.getLogger("MovieYearFetcher")

# Set your TMDb API key
tmdb.API_KEY = "b043bef236e1b972f25dcb382ef1af76"


def fetch_movie_year_tmdb(title: str) -> int | None:
    """
    Synchronous TMDb fetch.
    """
    try:
        search = tmdb.Search()
        response = search.movie(query=title)
        results = response.get("results", [])

        if not results:
            logger.warning(f"⚠️ TMDb: No results found for '{title}'")
            return None

        movie_data = results[0]
        release_date = movie_data.get("release_date")
        if release_date and len(release_date) >= 4:
            year = int(release_date[:4])
            save_movie_year(title, year)
            logger.info(f"✅ TMDb: Saved {title} → {year}")
            return year

        return None

    except Exception as e:
        logger.exception(f"❌ TMDb fetch failed for '{title}': {e}")
        return None

def clean_movie_title(title: str) -> str:
    """Extract clean movie title for TMDb query."""
    try:
        data = parse_title(title, translate_languages=True)
        name = data.get("title")
        if name:
            return name.strip()
    except Exception:
        pass
    # Fallback: remove common tags manually
    name = re.sub(r"(\b\d{3,4}p\b|\b4k\b|\bWEBRip\b|\bHDRip\b|\bBluRay\b|\bNF\b|\bAMZN\b)", "", title, flags=re.I)
    return name.strip()
    
async def get_or_fetch_movie_year(title: str) -> int | None:
    """
    Async wrapper for TMDb fetch to avoid blocking event loop.
    """
    # 1️⃣ Check DB
    title = clean_movie_title(title) 
    year = get_movie_year(title)
    if year:
        logger.info(f"📦 Found in DB: {title} → {year}")
        return year

    # 2️⃣ Fetch from TMDb asynchronously using executor
    logger.info(f"🔍 Year missing for '{title}', fetching via TMDb...")
    loop = asyncio.get_running_loop()
    year = await loop.run_in_executor(None, fetch_movie_year_tmdb, title)

    if year:
        logger.info(f"✅ Movie year obtained: {title} → {year}")
    else:
        logger.warning(f"⚠️ Could not fetch year for '{title}'")

    return year
