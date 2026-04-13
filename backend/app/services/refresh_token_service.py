"""Refresh Token 服务：基于 Redis 实现旋转刷新（Rolling Refresh）。

Key 设计：rt:{jti}  →  user_id（字符串），TTL = jwt_refresh_token_expire_days * 86400
旋转策略：每次刷新都删除旧 jti、写入新 jti，确保一个 refresh token 只能用一次。
"""
from app.core.redis_client import get_redis
from app.config import settings

_TTL = settings.jwt_refresh_token_expire_days * 86400
_PREFIX = "rt:"


def _key(jti: str) -> str:
    return f"{_PREFIX}{jti}"


async def store_refresh_token(jti: str, user_id: int) -> None:
    """登录 / 旋转刷新时，将新 jti 存入 Redis"""
    redis = await get_redis()
    await redis.setex(_key(jti), _TTL, str(user_id))


async def get_user_id_by_jti(jti: str) -> int | None:
    """根据 jti 查找对应 user_id；不存在或已过期返回 None"""
    redis = await get_redis()
    value = await redis.get(_key(jti))
    return int(value) if value else None


async def revoke_refresh_token(jti: str) -> None:
    """注销指定 jti（登出 / 旋转时删旧 key）"""
    redis = await get_redis()
    await redis.delete(_key(jti))
