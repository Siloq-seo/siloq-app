"""Redis connection for BullMQ"""
import redis.asyncio as aioredis
from app.core.config import settings


class RedisClient:
    """Redis client singleton"""
    _instance = None
    _client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def connect(self):
        """Connect to Redis"""
        if self._client is None:
            self._client = await aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._client

    async def disconnect(self):
        """Disconnect from Redis"""
        if self._client:
            await self._client.close()
            self._client = None

    async def get_client(self):
        """Get Redis client"""
        if self._client is None:
            await self.connect()
        return self._client


redis_client = RedisClient()

