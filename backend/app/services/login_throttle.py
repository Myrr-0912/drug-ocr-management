import redis.asyncio as aioredis
from app.config import settings
from app.core.redis_client import get_redis_client

# Redis key 前缀
_USER_PREFIX = "login_fail:"
_IP_PREFIX = "login_fail:ip:"


def _user_key(username: str) -> str:
    return f"{_USER_PREFIX}{username}"


def _ip_key(ip: str) -> str:
    return f"{_IP_PREFIX}{ip}"


async def is_locked(username: str, ip: str | None) -> bool:
    """检查账号或 IP 是否因连续失败而被锁定"""
    redis: aioredis.Redis = get_redis_client()
    count = await redis.get(_user_key(username))
    if count and int(count) >= settings.login_max_failures:
        return True
    if ip:
        ip_count = await redis.get(_ip_key(ip))
        if ip_count and int(ip_count) >= settings.login_max_failures:
            return True
    return False


async def record_failure(username: str, ip: str | None) -> None:
    """记录一次登录失败，超过阈值后锁定 lockout_minutes 分钟"""
    redis: aioredis.Redis = get_redis_client()
    ttl = settings.login_lockout_minutes * 60

    # 按用户名计数
    user_key = _user_key(username)
    await redis.incr(user_key)
    await redis.expire(user_key, ttl)

    # 按 IP 计数
    if ip:
        ip_key = _ip_key(ip)
        await redis.incr(ip_key)
        await redis.expire(ip_key, ttl)


async def clear_failures(username: str, ip: str | None) -> None:
    """登录成功时清除失败计数"""
    redis: aioredis.Redis = get_redis_client()
    await redis.delete(_user_key(username))
    if ip:
        await redis.delete(_ip_key(ip))
