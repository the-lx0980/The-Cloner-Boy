import logging
from pymongo import MongoClient, ASCENDING
from pymongo.errors import DuplicateKeyError

# -------------------------------
# 🧠 Logging Setup
# -------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -------------------------------
# ⚙️ MongoDB Connection Setup
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
# 🧩 CREATE UNIQUE INDEX (Prevent Duplicates)
# ====================================================
if collection:
    try:
        collection.create_index(
            [("title", ASCENDING), ("season", ASCENDING), ("type", ASCENDING)],
            unique=True
        )
        logger.info("🔒 Unique index created successfully.")
    except Exception as e:
        logger.warning(f"⚠️ Index creation skipped: {e}")


# ====================================================
# 🧠 COMMON HELPERS
# ====================================================
def normalize_title(title: str) -> str:
    """Normalize title to avoid case-sensitive duplicates"""
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
    except DuplicateKeyError:
        logger.warning(f"⚠️ Duplicate movie ignored: {title}")
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
        logger.info(f"✅ Saved Series: {title.title()} S{season} → {year}")
    except DuplicateKeyError:
        logger.warning(f"⚠️ Duplicate series ignored: {title.title()} S{season}")
    except Exception as e:
        logger.error(f"❌ Failed to save series {title} S{season}: {e}")


# ====================================================
# 📺 ANIME FUNCTIONS
# ====================================================
def save_anime(title: str, season: int, year: int):
    """Save or update anime info (title, season, year)"""
    if collection is None:
        return

    title = normalize_title(title)
    try:
        collection.update_one(
            {"title": title, "season": season, "type": "anime"},
            {"$set": {"year": year}},
            upsert=True
        )
        logger.info(f"✅ Saved Anime: {title.title()} S{season} → {year}")
    except DuplicateKeyError:
        logger.warning(f"⚠️ Duplicate entry ignored for {title.title()} S{season}")
    except Exception as e:
        logger.error(f"❌ Failed to save anime {title} S{season}: {e}")


def get_anime_year(title: str, season: int) -> int | None:
    """Fetch anime release year for a specific season"""
    if collection is None:
        return None

    title = normalize_title(title)
    data = collection.find_one({"title": title, "season": season, "type": "anime"})
    return data.get("year") if data else None


def list_anime():
    """List all saved anime"""
    if collection is None:
        print("⚠️ No MongoDB connection.")
        return []

    docs = list(collection.find({"type": "anime"}, {"_id": 0}))
    if not docs:
        print("📭 No anime saved yet.")
    else:
        print("📺 --- Saved Anime List ---")
        for d in docs:
            print(f"{d.get('title', '?').title()} (S{d.get('season')}) → {d.get('year')}")
    return docs


def delete_anime(title: str, season: int | None = None):
    """Delete anime entry"""
    if collection is None:
        return

    title = normalize_title(title)
    query = {"title": title, "type": "anime"}
    if season:
        query["season"] = season

    result = collection.delete_many(query)
    if result.deleted_count > 0:
        logger.info(f"🗑️ Deleted {result.deleted_count} record(s) for {title.title()} (S{season if season else 'All'})")
    else:
        logger.warning(f"⚠️ No record found for {title.title()} (S{season if season else 'All'})")


# ====================================================
# 🧾 LIST / DELETE ALL MEDIA
# ====================================================
def list_all_media():
    if collection is None:
        print("⚠️ No MongoDB connection.")
        return []

    docs = list(collection.find({}, {"_id": 0}))
    for d in docs:
        if d.get("type") == "movie":
            print(f"🎬 {d.get('title','?').title()} → {d.get('year')}")
        elif d.get("type") == "series":
            print(f"📺 {d.get('title','?').title()} S{d.get('season')} → {d.get('year')}")
        elif d.get("type") == "anime":
            print(f"🌸 {d.get('title','?').title()} S{d.get('season')} → {d.get('year')}")
    return docs


def delete_media(title: str, season: int | None = None, media_type: str | None = None):
    """Delete any media by title and optional season/type"""
    if collection is None:
        return

    title = normalize_title(title)
    query = {"title": title}
    if media_type:
        query["type"] = media_type
    if season:
        query["season"] = season

    result = collection.delete_many(query)
    logger.info(f"🗑️ Deleted {result.deleted_count} record(s) for {title.title()}")
