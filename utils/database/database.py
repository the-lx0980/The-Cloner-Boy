import logging
from pymongo import MongoClient

logger = logging.getLogger(__name__)

# -------------------------------
# MongoDB Connection Setup
# -------------------------------
try:
    client = MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=5000)
    db = client["media_db"]
    collection = db["media_info"]
    client.server_info()  # test connection
    logger.info("✅ Connected to MongoDB successfully.")
except Exception as e:
    logger.error(f"❌ MongoDB connection failed: {e}")
    collection = None


# ====================================================
# 🧠 COMMON HELPERS
# ====================================================

def normalize_title(title: str) -> str:
    """Normalize title for consistent storage."""
    return title.strip().lower()


# ====================================================
# 🎬 MOVIE FUNCTIONS
# ====================================================

def get_movie_year(title: str) -> int | None:
    """Fetch movie release year from MongoDB."""
    if not collection:
        return None

    title = normalize_title(title)
    data = collection.find_one({"title": title, "type": "movie"})
    return data.get("year") if data else None


def save_movie_year(title: str, year: int):
    """Save or update a movie's release year."""
    if not collection:
        return

    title = normalize_title(title)
    try:
        collection.update_one(
            {"title": title, "type": "movie"},
            {"$set": {"year": year}},
            upsert=True
        )
        logger.info(f"✅ Saved Movie: {title} → {year}")
    except Exception as e:
        logger.error(f"❌ Failed to save movie {title}: {e}")


# ====================================================
# 📺 SERIES FUNCTIONS
# ====================================================

def get_series_year(title: str, season: int) -> int | None:
    """Fetch series release year (per season) from MongoDB."""
    if not collection:
        return None

    title = normalize_title(title)
    data = collection.find_one({"title": title, "season": season, "type": "series"})
    return data.get("year") if data else None


def save_series_year(title: str, season: int, year: int):
    """Save or update a series' release year (per season)."""
    if not collection:
        return

    title = normalize_title(title)
    try:
        collection.update_one(
            {"title": title, "season": season, "type": "series"},
            {"$set": {"year": year}},
            upsert=True
        )
        logger.info(f"✅ Saved Series: {title} S{season} → {year}")
    except Exception as e:
        logger.error(f"❌ Failed to save series {title} S{season}: {e}")


# ====================================================
# 🧾 UTILS
# ====================================================

def list_all_media():
    """List all stored movies and series."""
    if not collection:
        print("⚠️ No MongoDB connection.")
        return []

    docs = list(collection.find({}, {"_id": 0}))
    for d in docs:
        if d.get("type") == "movie":
            print(f"🎬 {d.get('title','?')} → {d.get('year')}")
        else:
            print(f"📺 {d.get('title','?')} - S{d.get('season')} → {d.get('year')}")
    return docs


def delete_media(title: str, season: int | None = None):
    """Delete specific movie or series record."""
    if not collection:
        return

    title = normalize_title(title)
    query = {"title": title}
    if season:
        query["season"] = season
        query["type"] = "series"
    else:
        query["type"] = "movie"

    collection.delete_one(query)
    logger.info(f"🗑️ Deleted record for {title} (Season {season if season else 'Movie'})")
