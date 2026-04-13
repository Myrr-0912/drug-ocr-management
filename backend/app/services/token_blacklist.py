import redis.asyncio as aioredis
from app.core.redis_client import get_redis_client

# Redis key 前缀
_PREFIX = "bl:jti:"


async def blacklist_token(jti: str, ttl_seconds: int) -> None:
    """将 jti 加入黑名单，TTL 与 token 剩余有效期对齐"""
    if ttl_seconds <= 0:
        return  # token 已过期，无需写入
    redis: aioredis.Redis = get_redis_client()
    await redis.setex(f"{_PREFIX}{jti}", ttl_seconds, "1")


async def is_blacklisted(jti: str) -> bool:
    """检查 jti 是否在黑名单中"""
    redis: aioredis.Redis = get_redis_client()
    return await redis.exists(f"{_PREFIX}{jti}") == 1
