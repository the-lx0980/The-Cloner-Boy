import logging
import os
from typing import List, Dict, Optional
from pymongo import MongoClient, ASCENDING
from pymongo.collection import Collection
from dotenv import load_dotenv

load_dotenv()  

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def connect_to_mongodb() -> Optional[Collection]:
    """Connect to MongoDB and return the media_info collection."""
    mongo_uri = os.getenv("MONGODB_URI")
    if not mongo_uri:
        logger.error("❌ MONGODB_URI environment variable not set.")
        return None

    try:
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        client.server_info()  # Test connection
        db = client["media_db"]
        collection = db["media_info"]
        logger.info("✅ Connected to MongoDB successfully.")
        return collection
    except Exception as e:
        logger.error(f"❌ MongoDB connection failed: {e}")
        return None

collection = connect_to_mongodb()

def create_unique_index(col: Collection) -> None:
    """Create a unique index on title, season, and type."""
    try:
        col.create_index(
            [("title", ASCENDING), ("season", ASCENDING), ("type", ASCENDING)],
            unique=True
        )
        logger.info("🔒 Unique index created successfully.")
    except Exception as e:
        logger.warning(f"⚠️ Index creation skipped: {e}")

if collection is None:
    create_unique_index(collection)

def normalize_title(title: str) -> str:
    """Normalize title: lowercase, strip, collapse inner spaces."""
    if not title or not title.strip():
        raise ValueError("Title cannot be empty or None.")
    return " ".join(title.strip().lower().split())

def validate_year(year: int) -> None:
    if not isinstance(year, int) or year < 1888:
        raise ValueError(f"Invalid year: {year}. Must be >= 1888.")

def validate_season(season: int) -> None:
    if not isinstance(season, int) or season < 1:
        raise ValueError(f"Invalid season: {season}. Must be positive.")

def requires_connection(func):
    def wrapper(*args, **kwargs):
        if collection is None:
            logger.warning("⚠️ No MongoDB connection.")
            if "get" in func.__name__:
                return None
            return False
        return func(*args, **kwargs)
    return wrapper

@requires_connection
def get_movie_year(title: str) -> Optional[int]:
    title = normalize_title(title)
    doc = collection.find_one({"title": title, "type": "movie", "season": None})
    return doc.get("year") if doc else None

@requires_connection
def save_movie_year(title: str, year: int) -> bool:
    title = normalize_title(title)
    validate_year(year)
    collection.update_one(
        {"title": title, "type": "movie", "season": None},
        {"$set": {"year": year}},
        upsert=True
    )
    logger.info(f"✅ Saved Movie: {title.title()} → {year}")
    return True

@requires_connection
def get_series_year(title: str, season: int) -> Optional[int]:
    title = normalize_title(title)
    validate_season(season)
    doc = collection.find_one({"title": title, "type": "series", "season": season})
    return doc.get("year") if doc else None

@requires_connection
def save_series_year(title: str, season: int, year: int) -> bool:
    title = normalize_title(title)
    validate_season(season)
    validate_year(year)
    collection.update_one(
        {"title": title, "type": "series", "season": season},
        {"$set": {"year": year}},
        upsert=True
    )
    logger.info(f"✅ Saved Series: {title.title()} S{season} → {year}")
    return True

@requires_connection
def get_anime_year(title: str, season: int) -> Optional[int]:
    title = normalize_title(title)
    validate_season(season)
    doc = collection.find_one({"title": title, "type": "anime", "season": season})
    return doc.get("year") if doc else None

@requires_connection
def save_anime(title: str, season: int, year: int) -> bool:
    title = normalize_title(title)
    validate_season(season)
    validate_year(year)
    collection.update_one(
        {"title": title, "type": "anime", "season": season},
        {"$set": {"year": year}},
        upsert=True
    )
    logger.info(f"✅ Saved Anime: {title.title()} S{season} → {year}")
    return True

@requires_connection
def list_anime(skip: int = 0, limit: int = 100) -> List[Dict]:
    return list(collection.find({"type": "anime"}, {"_id": 0}).skip(skip).limit(limit))

@requires_connection
def print_anime_list() -> None:
    docs = list_anime()
    if not docs:
        print("📭 No anime saved yet.")
        return
    print("📺 --- Saved Anime List ---")
    for d in docs:
        print(f"{d.get('title', '?').title()} (S{d.get('season')}) → {d.get('year')}")

@requires_connection
def delete_anime(title: str, season: Optional[int] = None) -> int:
    title = normalize_title(title)
    query = {"title": title, "type": "anime"}
    if season is not None:
        validate_season(season)
        query["season"] = season
    result = collection.delete_many(query)
    count = result.deleted_count
    if count:
        logger.info(f"🗑️ Deleted {count} record(s) for {title.title()} (S{season if season else 'All'})")
    else:
        logger.warning(f"⚠️ No record found for {title.title()} (S{season if season else 'All'})")
    return count

@requires_connection
def list_all_media(skip: int = 0, limit: int = 100) -> List[Dict]:
    return list(collection.find({}, {"_id": 0}).skip(skip).limit(limit))

@requires_connection
def print_all_media() -> None:
    docs = list_all_media()
    if not docs:
        print("📭 No media saved yet.")
        return
    print("📚 --- All Media List ---")
    for d in docs:
        t = d.get("type")
        title = d.get("title", "?").title()
        season = d.get("season")
        year = d.get("year")
        if t == "movie":
            print(f"🎬 {title} → {year}")
        elif t == "series":
            print(f"📺 {title} S{season} → {year}")
        elif t == "anime":
            print(f"🌸 {title} S{season} → {year}")

@requires_connection
def delete_media(title: str, season: Optional[int] = None, media_type: Optional[str] = None) -> int:
    title = normalize_title(title)
    query = {"title": title}
    if media_type:
        if media_type not in ["movie", "series", "anime"]:
            raise ValueError(f"Invalid media type: {media_type}")
        query["type"] = media_type
    if season is not None:
        validate_season(season)
        query["season"] = season
    elif media_type == "movie":
        query["season"] = None

    result = collection.delete_many(query)
    count = result.deleted_count
    logger.info(f"🗑️ Deleted {count} record(s) for {title.title()}")
    return count
