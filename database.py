from motor.motor_asyncio import AsyncIOMotorClient
from config import Config
import logging

logger = logging.getLogger(__name__)

class Database:
    client = None
    db = None

    @classmethod
    async def connect(cls):
        if not Config.MONGO_URI:
            logger.warning("MONGO_URI not set. Database will not be connected.")
            return

        try:
            import certifi
            cls.client = AsyncIOMotorClient(
                Config.MONGO_URI,
                tlsCAFile=certifi.where(),
                serverSelectionTimeoutMS=5000
            )
            # Verify connection
            await cls.client.admin.command('ping')
            # Use default database from URI, or fallback to 'atlas'
            try:
                cls.db = cls.client.get_default_database()
            except:
                cls.db = cls.client.get_database("atlas")
            
            logger.info(f"Connected to MongoDB successfully. Database: {cls.db.name}")
        except Exception as e:
            logger.error(f"MongoDB Connection Error: {e}")
            cls.client = None
            cls.db = None

    @classmethod
    async def close(cls):
        if cls.client:
            cls.client.close()
            logger.info("MongoDB connection closed.")
