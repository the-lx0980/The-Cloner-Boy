"""
import logging
import requests
from database import save_anime, get_anime_year as db_get_anime_year

ANILIST_API_URL = "https://graphql.anilist.co"

# Logger Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ====================================================
# 🧠 Generate Title Variations
# ====================================================
def generate_search_titles(title: str, season_number: int):
    """Generate search variations using English, Romaji, and Japanese titles."""
    base_variations = [
        f"{title} Season {season_number}",
        f"{title} Part {season_number}",
        f"{title} {season_number}",
        f"{title} {season_number}th Season",
        f"{title} Final Season",
        f"{title} Arc {season_number}",
        f"{title} TV Season {season_number}",
        f"{title} Special Season {season_number}",
    ]

    # -----------------------------
    # 🔍 Fetch alternative titles from AniList
    # -----------------------------
    query = '''
    query ($search: String) {
      Media(search: $search, type: ANIME) {
        title { romaji native english }
        synonyms
      }
    }
    '''
    try:
        response = requests.post(ANILIST_API_URL, json={"query": query, "variables": {"search": title}})
        response.raise_for_status()
        media = response.json().get("data", {}).get("Media")

        if media:
            romaji = media["title"].get("romaji")
            native = media["title"].get("native")
            english = media["title"].get("english")
            synonyms = media.get("synonyms", [])

            alt_titles = [romaji, native, english] + synonyms
            for t in filter(None, alt_titles):
                base_variations += [
                    f"{t} Season {season_number}",
                    f"{t} Part {season_number}",
                    f"{t} {season_number}",
                    f"{t} Final Season",
                    f"{t} Arc {season_number}",
                ]

    except requests.RequestException as e:
        logger.warning(f"⚠️ AniList title fetch failed for '{title}': {e}")

    # Deduplicate and clean
    clean = list(dict.fromkeys(v.strip() for v in base_variations if v))
    return clean


# ====================================================
# 🎬 Fetch Anime Year (from AniList)
# ====================================================
def fetch_anime_year(title: str, season_number: int) -> int | None:
    """Try multiple search variations to find correct release year."""
    variations = generate_search_titles(title, season_number)
    query = '''
    query ($search: String) {
      Media(search: $search, type: ANIME) {
        title { romaji }
        startDate { year }
      }
    }
    '''

    for name in variations:
        try:
            response = requests.post(ANILIST_API_URL, json={"query": query, "variables": {"search": name}})
            response.raise_for_status()
            data = response.json().get("data", {}).get("Media")

            if data and data.get("startDate", {}).get("year"):
                year = data["startDate"]["year"]
                romaji_title = data["title"]["romaji"]
                logger.info(f"✅ {romaji_title} Season {season_number}: {year}")
                save_anime(title, season_number, year)
                return year
        except requests.RequestException:
            continue

    logger.warning(f"❌ Could not find release year for '{title}' Season {season_number}")
    return None


# ====================================================
# ⚙️ Main Function — Auto Fetch or Use DB
# ====================================================
def get_or_fetch_anime_year(title: str, season: int) -> int | None:
    """1. Check MongoDB, else 2. Fetch from AniList and save."""
    year = db_get_anime_year(title, season)
    if year:
        logger.info(f"📦 Found in DB: {title} S{season} → {year}")
        return year

    logger.info(f"🔍 Fetching from AniList for {title} S{season}...")
    return fetch_anime_year(title, season)
"""
