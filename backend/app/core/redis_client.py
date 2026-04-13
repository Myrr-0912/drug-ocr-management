import logging
import redis.asyncio as aioredis
from typing import AsyncGenerator
from app.config import settings

logger = logging.getLogger(__name__)

# 全局 Redis 连接池单例
_redis_pool: aioredis.Redis | None = None


async def init_redis() -> None:
    """初始化 Redis 连接池（在 lifespan startup 中调用）"""
    global _redis_pool
    _redis_pool = aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
        max_connections=20,
    )
    # 验证连接可用
    await _redis_pool.ping()
    logger.info("Redis 连接池已初始化：%s", settings.redis_url)


async def close_redis() -> None:
    """关闭 Redis 连接池（在 lifespan shutdown 中调用）"""
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.aclose()
        _redis_pool = None
        logger.info("Redis 连接池已关闭")


def get_redis_client() -> aioredis.Redis:
    """获取全局 Redis 客户端（非依赖注入版本，供 service 层直接调用）"""
    if _redis_pool is None:
        raise RuntimeError("Redis 连接池未初始化，请检查 lifespan 配置")
    return _redis_pool


async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    """FastAPI 依赖注入版本"""
    yield get_redis_client()
