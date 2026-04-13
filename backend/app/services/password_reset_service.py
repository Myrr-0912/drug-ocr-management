"""密码重置 Token 服务。

流程：
  1. forgot_password 生成 UUID token → 存 Redis `pwd_reset:{token}` = user_id，TTL 15 分钟
  2. reset_password 查 Redis → 校验 → 改密码 → 删 key（防二次使用）
"""
import uuid
from app.core.redis_client import get_redis

_TTL_SECONDS = 15 * 60      # 15 分钟有效
_PREFIX = "pwd_reset:"


def _key(token: str) -> str:
    return f"{_PREFIX}{token}"


async def create_reset_token(user_id: int) -> str:
    """生成重置 token 并存入 Redis，返回 token 字符串"""
    token = str(uuid.uuid4())
    redis = await get_redis()
    await redis.setex(_key(token), _TTL_SECONDS, str(user_id))
    return token


async def get_user_id_by_token(token: str) -> int | None:
    """根据 token 查 user_id；不存在或过期返回 None"""
    redis = await get_redis()
    value = await redis.get(_key(token))
    return int(value) if value else None


async def revoke_reset_token(token: str) -> None:
    """使用后立即作废 token（防重放）"""
    redis = await get_redis()
    await redis.delete(_key(token))
