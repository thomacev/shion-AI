from redis.asyncio import Redis
from app.core.config import settings

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

        except Exception:
            redis_client = None

    return redis_client


async def close_redis():
    global redis_client

    if redis_client:
        await redis_client.aclose()
        redis_client = None
