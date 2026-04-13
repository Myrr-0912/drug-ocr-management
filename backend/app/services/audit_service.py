from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.login_log import LoginLog
from app.models.user import User


def _get_client_ip(request: Request) -> str | None:
    """获取真实客户端 IP（兼容反向代理转发头）"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


async def log_login(
    db: AsyncSession,
    *,
    request: Request,
    username: str,
    success: bool,
    user: User | None = None,
    failure_reason: str | None = None,
) -> None:
    """写入登录审计日志"""
    log = LoginLog(
        username=username,
        user_id=user.id if user else None,
        ip=_get_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
        success=success,
        failure_reason=failure_reason,
    )
    db.add(log)
    await db.flush()
