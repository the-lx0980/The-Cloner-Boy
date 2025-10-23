import logging
import os
from typing import List, Dict, Optional
from pymongo import MongoClient, ASCENDING
from pymongo.errors import DuplicateKeyError
from pymongo.collection import Collection
from dotenv import load_dotenv

# -------------------------------
# 🧠 Logging Setup
# -------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -------------------------------
# ⚙️ MongoDB Connection Setup
# -------------------------------
def connect_to_mongodb() -> Collection:
    """Establish a connection to MongoDB and return the media_info collection.
    
    Returns:
        Collection: The MongoDB collection for media_info.
        
    Raises:
        ConnectionError: If connection to MongoDB fails.
    """
    load_dotenv()
    mongo_uri = os.getenv("MONGODB_URI")
    if not mongo_uri:
        logger.error("❌ MONGODB_URI environment variable not set.")
        raise ConnectionError("MongoDB URI not found in environment variables.")
    
    try:
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        client.server_info()  # Test connection
        db = client["media_db"]
        collection = db["media_info"]
        logger.info("✅ Connected to MongoDB successfully.")
        return collection
    except Exception as e:
        logger.error(f"❌ MongoDB connection failed: {e}")
        raise ConnectionError(f"Failed to connect to MongoDB: {e}")

# Initialize collection
try:
    collection = connect_to_mongodb()
except ConnectionError:
    collection = None

# -------------------------------
# 🔒 Create Unique Index
# -------------------------------
def create_unique_index(collection: Optional[Collection]) -> None:
    """Create a unique index on title, season, and type to prevent duplicates.
    
    Args:
        collection (Optional[Collection]): The MongoDB collection.
    """
    if collection is None:
        logger.warning("⚠️ No MongoDB connection. Skipping index creation.")
        return

    try:
        collection.create_index(
            [("title", ASCENDING), ("season", ASCENDING), ("type", ASCENDING)],
            unique=True
        )
        logger.info("🔒 Unique index created successfully.")
    except Exception as e:
        logger.warning(f"⚠️ Index creation skipped: {e}")

if collection:
    create_unique_index(collection)

# -------------------------------
# 🧠 Common Helpers
# -------------------------------
def normalize_title(title: str) -> str:
    """Normalize a title by converting to lowercase and removing leading/trailing whitespace.
    
    Args:
        title (str): The title to normalize.
        
    Returns:
        str: The normalized title.
        
    Raises:
        ValueError: If the title is empty or None.
    """
    if not title or not title.strip():
        raise ValueError("Title cannot be empty or None.")
    return title.strip().lower()

def handle_duplicate_error(e: DuplicateKeyError, media_type: str, title: str, season: Optional[int] = None) -> None:
    """Handle duplicate key errors with consistent logging.
    
    Args:
        e (DuplicateKeyError): The duplicate key error.
        media_type (str): The type of media (movie, series, anime).
        title (str): The title of the media.
        season (Optional[int]): The season number, if applicable.
    """
    logger.warning(f"⚠️ Duplicate {media_type} ignored: {title.title()}{' S' + str(season) if season else ''}")

def validate_year(year: int) -> None:
    """Validate that a year is reasonable (after 1888, the first film year).
    
    Args:
        year (int): The year to validate.
        
    Raises:
        ValueError: If the year is invalid.
    """
    if not isinstance(year, int) or year < 1888:
        raise ValueError(f"Invalid year: {year}. Must be an integer >= 1888.")

def validate_season(season: int) -> None:
    """Validate that a season number is positive.
    
    Args:
        season (int): The season number to validate.
        
    Raises:
        ValueError: If the season is invalid.
    """
    if not isinstance(season, int) or season < 1:
        raise ValueError(f"Invalid season: {season}. Must be a positive integer.")

# -------------------------------
# 🎬 Movie Functions
# -------------------------------
def get_movie_year(title: str) -> Optional[int]:
    """Fetch the release year for a movie.
    
    Args:
        title (str): The movie title.
        
    Returns:
        Optional[int]: The release year, or None if not found or no connection.
    """
    if collection is None:
        logger.warning("⚠️ No MongoDB connection.")
        return None

    try:
        title = normalize_title(title)
        data = collection.find_one({"title": title, "type": "movie", "season": None})
        return data.get("year") if data else None
    except ValueError as e:
        logger.error(f"❌ Failed to get movie year: {e}")
        return None

def save_movie_year(title: str, year: int) -> bool:
    """Save or update a movie's release year.
    
    Args:
        title (str): The movie title.
        year (int): The release year.
        
    Returns:
        bool: True if saved successfully, False otherwise.
    """
    if collection is None:
        logger.warning("⚠️ No MongoDB connection.")
        return False

    try:
        title = normalize_title(title)
        validate_year(year)
        collection.update_one(
            {"title": title, "type": "movie", "season": None},
            {"$set": {"year": year}},
            upsert=True
        )
        logger.info(f"✅ Saved Movie: {title.title()} → {year}")
        return True
    except DuplicateKeyError as e:
        handle_duplicate_error(e, "movie", title)
        return False
    except (ValueError, Exception) as e:
        logger.error(f"❌ Failed to save movie {title}: {e}")
        return False

# -------------------------------
# 📺 Series Functions
# -------------------------------
def get_series_year(title: str, season: int) -> Optional[int]:
    """Fetch the release year for a specific season of a series.
    
    Args:
        title (str): The series title.
        season (int): The season number.
        
    Returns:
        Optional[int]: The release year, or None if not found or no connection.
    """
    if collection is None:
        logger.warning("⚠️ No MongoDB connection.")
        return None

    try:
        title = normalize_title(title)
        validate_season(season)
        data = collection.find_one({"title": title, "season": season, "type": "series"})
        return data.get("year") if data else None
    except ValueError as e:
        logger.error(f"❌ Failed to get series year: {e}")
        return None

def save_series_year(title: str, season: int, year: int) -> bool:
    """Save or update a series' release year for a specific season.
    
    Args:
        title (str): The series title.
        season (int): The season number.
        year (int): The release year.
        
    Returns:
        bool: True if saved successfully, False otherwise.
    """
    if collection is None:
        logger.warning("⚠️ No MongoDB connection.")
        return False

    try:
        title = normalize_title(title)
        validate_season(season)
        validate_year(year)
        collection.update_one(
            {"title": title, "season": season, "type": "series"},
            {"$set": {"year": year}},
            upsert=True
        )
        logger.info(f"✅ Saved Series: {title.title()} S{season} → {year}")
        return True
    except DuplicateKeyError as e:
        handle_duplicate_error(e, "series", title, season)
        return False
    except (ValueError, Exception) as e:
        logger.error(f"❌ Failed to save series {title} S{season}: {e}")
        return False

# -------------------------------
# 📺 Anime Functions
# -------------------------------
def save_anime(title: str, season: int, year: int) -> bool:
    """Save or update anime info (title, season, year).
    
    Args:
        title (str): The anime title.
        season (int): The season number.
        year (int): The release year.
        
    Returns:
        bool: True if saved successfully, False otherwise.
    """
    if collection is None:
        logger.warning("⚠️ No MongoDB connection.")
        return False

    try:
        title = normalize_title(title)
        validate_season(season)
        validate_year(year)
        collection.update_one(
            {"title": title, "season": season, "type": "anime"},
            {"$set": {"year": year}},
            upsert=True
        )
        logger.info(f"✅ Saved Anime: {title.title()} S{season} → {year}")
        return True
    except DuplicateKeyError as e:
        handle_duplicate_error(e, "anime", title, season)
        return False
    except (ValueError, Exception) as e:
        logger.error(f"❌ Failed to save anime {title} S{season}: {e}")
        return False

def get_anime_year(title: str, season: int) -> Optional[int]:
    """Fetch the release year for a specific anime season.
    
    Args:
        title (str): The anime title.
        season (int): The season number.
        
    Returns:
        Optional[int]: The release year, or None if not found or no connection.
    """
    if collection is None:
        logger.warning("⚠️ No MongoDB connection.")
        return None

    try:
        title = normalize_title(title)
        validate_season(season)
        data = collection.find_one({"title": title, "season": season, "type": "anime"})
        return data.get("year") if data else None
    except ValueError as e:
        logger.error(f"❌ Failed to get anime year: {e}")
        return None

def list_anime(skip: int = 0, limit: int = 100) -> List[Dict]:
    """Fetch all saved anime entries with optional pagination.
    
    Args:
        skip (int): Number of documents to skip (default: 0).
        limit (int): Maximum number of documents to return (default: 100).
        
    Returns:
        List[Dict]: List of anime documents.
    """
    if collection is None:
        logger.warning("⚠️ No MongoDB connection.")
        return []

    try:
        docs = list(collection.find({"type": "anime"}, {"_id": 0}).skip(skip).limit(limit))
        return docs
    except Exception as e:
        logger.error(f"❌ Failed to list anime: {e}")
        return []

def print_anime_list() -> None:
    """Print all saved anime entries."""
    docs = list_anime()
    if not docs:
        print("📭 No anime saved yet.")
    else:
        print("📺 --- Saved Anime List ---")
        for d in docs:
            print(f"{d.get('title', '?').title()} (S{d.get('season')}) → {d.get('year')}")

def delete_anime(title: str, season: Optional[int] = None) -> int:
    """Delete anime entries by title and optional season.
    
    Args:
        title (str): The anime title.
        season (Optional[int]): The season number to delete (None to delete all seasons).
        
    Returns:
        int: Number of records deleted.
    """
    if collection is None:
        logger.warning("⚠️ No MongoDB connection.")
        return 0

    try:
        title = normalize_title(title)
        query = {"title": title, "type": "anime"}
        if season is not None:
            validate_season(season)
            query["season"] = season

        result = collection.delete_many(query)
        deleted_count = result.deleted_count
        if deleted_count > 0:
            logger.info(f"🗑️ Deleted {deleted_count} record(s) for {title.title()} (S{season if season else 'All'})")
        else:
            logger.warning(f"⚠️ No record found for {title.title()} (S{season if season else 'All'})")
        return deleted_count
    except ValueError as e:
        logger.error(f"❌ Failed to delete anime: {e}")
        return 0

# -------------------------------
# 🧾 List / Delete All Media
# -------------------------------
def list_all_media(skip: int = 0, limit: int = 100) -> List[Dict]:
    """Fetch all media entries (movies, series, anime) with optional pagination.
    
    Args:
        skip (int): Number of documents to skip (default: 0).
        limit (int): Maximum number of documents to return (default: 100).
        
    Returns:
        List[Dict]: List of media documents.
    """
    if collection is None:
        logger.warning("⚠️ No MongoDB connection.")
        return []

    try:
        docs = list(collection.find({}, {"_id": 0}).skip(skip).limit(limit))
        return docs
    except Exception as e:
        logger.error(f"❌ Failed to list media: {e}")
        return []

def print_all_media() -> None:
    """Print all media entries (movies, series, anime)."""
    docs = list_all_media()
    if not docs:
        print("📭 No media saved yet.")
    else:
        print("📚 --- All Media List ---")
        for d in docs:
            if d.get("type") == "movie":
                print(f"🎬 {d.get('title', '?').title()} → {d.get('year')}")
            elif d.get("type") == "series":
                print(f"📺 {d.get('title', '?').title()} S{d.get('season')} → {d.get('year')}")
            elif d.get("type") == "anime":
                print(f"🌸 {d.get('title', '?').title()} S{d.get('season')} → {d.get('year')}")

def delete_media(title: str, season: Optional[int] = None, media_type: Optional[str] = None) -> int:
    """Delete media entries by title, optional season, and optional media type.
    
    Args:
        title (str): The media title.
        season (Optional[int]): The season number to delete (None for all seasons).
        media_type (Optional[str]): The media type (movie, series, anime; None for all types).
        
    Returns:
        int: Number of records deleted.
    """
    if collection is None:
        logger.warning("⚠️ No MongoDB connection.")
        return 0

    try:
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
            query["season"] = None  # Ensure movies have season: None

        result = collection.delete_many(query)
        deleted_count = result.deleted_count
        logger.info(f"🗑️ Deleted {deleted_count} record(s) for {title.title()}")
        return deleted_count
    except ValueError as e:
        logger.error(f"❌ Failed to delete media: {e}")
        return 0
