from pymongo import MongoClient, ASCENDING
from pymongo.database import Database
from pymongo.collection import Collection
from config import Config
import logging

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.client: MongoClient | None = None
        self.db: Database | None = None
        
        self.users: Collection | None = None
        self.targets: Collection | None = None
        self.duplicates: Collection | None = None

    def connect(self):
        try:
            self.client = MongoClient(Config.MONGO_URI, serverSelectionTimeoutMS=5000)
            # Force connection check
            self.client.admin.command("ping")
            
            self.db = self.client[Config.DB_NAME]
            
            self.users = self.db["users"]
            self.targets = self.db["targets"]
            self.duplicates = self.db["duplicates"]
            
            self._create_indexes()
            logger.info("✅ MongoDB connected successfully")
            
        except Exception as e:
            logger.error(f"❌ MongoDB connection failed: {e}")
            raise

    def _create_indexes(self):
        # users
        self.users.create_index([("user_id", ASCENDING)], unique=True)
        
        # targets
        self.targets.create_index([("user_id", ASCENDING)])
        self.targets.create_index([("user_id", ASCENDING), ("chat_id", ASCENDING)], unique=True)
        
        # duplicates - MOST IMPORTANT
        self.duplicates.create_index(
            [
                ("user_id", ASCENDING),
                ("target_chat_id", ASCENDING),
                ("unique_file_id", ASCENDING)
            ],
            unique=True
        )
        
        logger.info("✅ Indexes created")

    def close(self):
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")


# Global instance
db = Database()
