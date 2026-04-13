from datetime import datetime, timezone
from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UnauthorizedError, ConflictError, BusinessError
from app.core.security import (
    hash_password, verify_password, create_access_token, decode_access_token
)
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, LoginRequest, TokenResponse, UserResponse
from app.services import login_throttle, audit_service
from app.services.token_blacklist import blacklist_token


async def register(db: AsyncSession, data: UserCreate) -> User:
    """注册新用户"""
    # 检查用户名是否已存在
    result = await db.execute(select(User).where(User.username == data.username))
    if result.scalar_one_or_none():
        raise ConflictError(f"用户名 '{data.username}' 已被注册")

    # 检查邮箱唯一性（email 非空时）
    if data.email:
        result = await db.execute(select(User).where(User.email == data.email))
        if result.scalar_one_or_none():
            raise ConflictError(f"邮箱 '{data.email}' 已被注册")

    user = User(
        username=data.username,
        password_hash=hash_password(data.password),
        real_name=data.real_name,
        phone=data.phone,
        email=data.email,
        role=UserRole.user,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def login(db: AsyncSession, data: LoginRequest, request: Request) -> TokenResponse:
    """用户登录，包含限流校验 + 审计日志"""
    ip = _get_ip(request)

    # 检查是否被限流锁定
    if await login_throttle.is_locked(data.username, ip):
        raise UnauthorizedError(
            f"账号已因连续失败登录被锁定，请 {_settings().login_lockout_minutes} 分钟后重试"
        )

    result = await db.execute(select(User).where(User.username == data.username))
    user = result.scalar_one_or_none()

    # 密码校验失败
    if not user or not verify_password(data.password, user.password_hash):
        await login_throttle.record_failure(data.username, ip)
        await audit_service.log_login(
            db, request=request, username=data.username,
            success=False, failure_reason="用户名或密码错误"
        )
        raise UnauthorizedError("用户名或密码错误")

    # 账号被禁用
    if not user.is_active:
        await audit_service.log_login(
            db, request=request, username=data.username,
            success=False, user=user, failure_reason="账号已被禁用"
        )
        raise UnauthorizedError("账号已被禁用，请联系管理员")

    # 登录成功：清除失败计数 + 写入审计日志
    await login_throttle.clear_failures(data.username, ip)
    await audit_service.log_login(
        db, request=request, username=data.username, success=True, user=user
    )

    token = create_access_token(subject=user.id, role=user.role.value)
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


async def logout(token: str) -> None:
    """注销 token：将 jti 写入 Redis 黑名单"""
    try:
        payload = decode_access_token(token)
        jti: str | None = payload.get("jti")
        exp: int | None = payload.get("exp")
        if not jti or not exp:
            return  # 旧格式 token，无 jti，不做处理
        now = int(datetime.now(timezone.utc).timestamp())
        ttl = exp - now
        await blacklist_token(jti, ttl)
    except Exception:
        pass  # token 已过期或无效，无需处理


async def change_password(
    db: AsyncSession, user: User, old_password: str, new_password: str
) -> None:
    """修改密码：校验旧密码后写入新哈希"""
    if not verify_password(old_password, user.password_hash):
        raise BusinessError("旧密码错误")
    user.password_hash = hash_password(new_password)
    await db.flush()


def _get_ip(request: Request) -> str | None:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def _settings():
    from app.config import settings
    return settings
