# app/core/redis.py
from redis.asyncio import Redis
from app.core.config import settings
from app.core.logger import logger

redis_client: Redis | None = None


async def get_redis_client() -> Redis | None:
    global redis_client

    if redis_client is None:
        try:
            redis_client = Redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            await redis_client.ping()
            logger.info("Redis client connected successfully")
        except Exception as e:
            logger.error("Failed to connect to Redis", extra={"error": str(e)})
            redis_client = None

    return redis_client


async def close_redis():
    global redis_client

    if redis_client:
        await redis_client.aclose()
        redis_client = None
        logger.info("Redis connection closed")