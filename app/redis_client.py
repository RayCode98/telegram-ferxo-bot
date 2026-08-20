from redis.asyncio import Redis

from app.config import settings

redis: Redis = Redis.from_url(
    settings.redis_url,
    decode_responses=True,
)


async def close_redis() -> None:
    await redis.aclose()
