import logging
from pymongo import MongoClient

logger = logging.getLogger(__name__)

# -------------------------------
# MongoDB Connection Setup
# -------------------------------
try:
    client = MongoClient(
        "mongodb+srv://kareem9075:C93PrxDdIQrtStxB@cluster0.j2xlpdt.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0",
        serverSelectionTimeoutMS=5000
    )
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
    return title.strip().lower()


# ====================================================
# 🎬 MOVIE FUNCTIONS
# ====================================================
def get_movie_year(title: str) -> int | None:
    if collection is None:
        return None

    title = normalize_title(title)
    data = collection.find_one({"title": title, "type": "movie"})
    return data.get("year") if data else None


def save_movie_year(title: str, year: int):
    if collection is None:
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
    if collection is None:
        return None

    title = normalize_title(title)
    data = collection.find_one({"title": title, "season": season, "type": "series"})
    return data.get("year") if data else None


def save_series_year(title: str, season: int, year: int):
    if collection is None:
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
    if collection is None:
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
    if collection is None:
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

====================================================
def save_anime(title: str, season: int, year: int):
    """Save or update anime info (title, season, year)"""
    if collection is None:
        return

    title = normalize_title(title)
    try:
        collection.update_one(
            {"title": title, "season": season},
            {"$set": {"year": year, "type": "anime"}},
            upsert=True
        )
        logger.info(f"✅ Saved: {title.title()} S{season} → {year}")
    except Exception as e:
        logger.error(f"❌ Failed to save {title} S{season}: {e}")


def get_anime_year(title: str, season: int) -> int | None:
    """Fetch anime release year for a specific season"""
    if collection is None:
        return None

    title = normalize_title(title)
    data = collection.find_one({"title": title, "season": season, "type": "anime"})
    if data:
        logger.info(f"📅 {title.title()} S{season} → {data.get('year')}")
        return data.get("year")
    else:
        logger.warning(f"⚠️ No data found for {title.title()} S{season}")
        return None


def list_anime():
    """List all saved anime"""
    if collection is None:
        print("⚠️ No MongoDB connection.")
        return []

    docs = list(collection.find({"type": "anime"}, {"_id": 0}))
    for d in docs:
        print(f"📺 {d.get('title', '?').title()} (S{d.get('season')}) → {d.get('year')}")
    return docs


def delete_anime(title: str, season: int | None = None):
    """Delete anime entry"""
    if collection is None:
        return

    title = normalize_title(title)
    query = {"title": title, "type": "anime"}
    if season:
        query["season"] = season

    collection.delete_many(query)
    logger.info(f"🗑️ Deleted {title.title()} (Season {season if season else 'All'})")
