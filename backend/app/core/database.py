from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.core.config import get_settings


class DatabaseManager:
    """Manages asynchronous connections to MongoDB Atlas / Local instance."""

    def __init__(self):
        self._client: Optional[AsyncIOMotorClient] = None
        self._db: Optional[AsyncIOMotorDatabase] = None

    def get_client(self) -> AsyncIOMotorClient:
        if self._client is None:
            settings = get_settings()
            self._client = AsyncIOMotorClient(settings.MONGODB_URI, serverSelectionTimeoutMS=5000)
        return self._client

    def get_database(self) -> AsyncIOMotorDatabase:
        if self._db is None:
            settings = get_settings()
            client = self.get_client()
            self._db = client[settings.MONGODB_DB_NAME]
        return self._db

    async def ping(self) -> bool:
        """Ping MongoDB to verify connection status."""
        try:
            client = self.get_client()
            await client.admin.command("ping")
            return True
        except Exception:
            return False

    def close(self):
        if self._client is not None:
            self._client.close()
            self._client = None
            self._db = None


db_manager = DatabaseManager()
