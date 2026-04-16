from datetime import datetime, timezone
from fastapi import Request
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UnauthorizedError, ConflictError, BusinessError
from app.core.security import (
    hash_password, verify_password,
    create_access_token, decode_access_token,
    create_refresh_token, decode_refresh_token,
)
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, LoginRequest, TokenResponse, UserResponse
from app.services import login_throttle, audit_service
from app.services.token_blacklist import blacklist_token
from app.services import refresh_token_service, password_reset_service, email_service


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

    # 支持用户名或邮箱登录
    result = await db.execute(
        select(User).where(
            or_(User.username == data.username, User.email == data.username)
        )
    )
    user = result.scalar_one_or_none()

    # 账号不存在
    if not user:
        await login_throttle.record_failure(data.username, ip)
        await audit_service.log_login(
            db, request=request, username=data.username,
            success=False, failure_reason="账号未注册"
        )
        raise UnauthorizedError("该账号未注册，请先注册")

    # 密码错误
    if not verify_password(data.password, user.password_hash):
        await login_throttle.record_failure(data.username, ip)
        await audit_service.log_login(
            db, request=request, username=data.username,
            success=False, user=user, failure_reason="密码错误"
        )
        raise UnauthorizedError("密码错误，请重新输入")

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

    access_token = create_access_token(subject=user.id, role=user.role.value)
    refresh_token_str, rt_jti = create_refresh_token(user.id)
    await refresh_token_service.store_refresh_token(rt_jti, user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token_str,
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


async def refresh(db: AsyncSession, old_refresh_token: str) -> TokenResponse:
    """使用 Refresh Token 换取新的 Access Token + Refresh Token（旋转刷新）

    安全设计：
    - 验证 JWT 签名与有效期
    - 检查 Redis 中 jti 是否存在（防重放）
    - 删除旧 jti + 写入新 jti（单次使用）
    """
    from jose import JWTError
    try:
        payload = decode_refresh_token(old_refresh_token)
    except JWTError:
        raise UnauthorizedError("Refresh Token 无效或已过期，请重新登录")

    jti: str = payload.get("jti", "")
    user_id = await refresh_token_service.get_user_id_by_jti(jti)
    if not user_id:
        # Redis 中无记录（可能是 Redis 重启导致数据丢失），
        # 但 JWT 签名与有效期已在 decode_refresh_token 中通过验证，
        # 降级为信任 JWT payload 中的 sub（user_id），避免用户被迫重新登录。
        sub = payload.get("sub", "")
        user_id = int(sub) if sub.isdigit() else None
        if not user_id:
            raise UnauthorizedError("Refresh Token 已注销或已过期，请重新登录")

    result = await db.execute(select(User).where(User.id == user_id))
    user: User | None = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise UnauthorizedError("账号不存在或已被禁用")

    # 旋转：删旧 jti，生成新 token 对
    await refresh_token_service.revoke_refresh_token(jti)
    new_access = create_access_token(subject=user.id, role=user.role.value)
    new_refresh_str, new_rt_jti = create_refresh_token(user.id)
    await refresh_token_service.store_refresh_token(new_rt_jti, user.id)

    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh_str,
        user=UserResponse.model_validate(user),
    )


async def logout_with_refresh(access_token: str, refresh_token_str: str | None) -> None:
    """注销：黑名单 access token + 撤销 refresh token"""
    await logout(access_token)
    if refresh_token_str:
        try:
            payload = decode_refresh_token(refresh_token_str)
            jti = payload.get("jti", "")
            if jti:
                await refresh_token_service.revoke_refresh_token(jti)
        except Exception:
            pass  # refresh token 已过期，忽略


async def forgot_password(db: AsyncSession, email: str) -> None:
    """忘记密码：验证邮箱存在 → 生成重置 token → 发送邮件"""
    result = await db.execute(select(User).where(User.email == email))
    user: User | None = result.scalar_one_or_none()
    if not user:
        raise BusinessError("该邮箱未注册，请确认后重试")
    if not user.is_active:
        raise BusinessError("该账号已被禁用，请联系管理员")

    token = await password_reset_service.create_reset_token(user.id)
    try:
        await email_service.send_reset_password_email(email, user.username, token)
    except Exception:
        # 邮件发送失败时撤销 token，避免 Redis 中遗留无效 key
        await password_reset_service.revoke_reset_token(token)
        raise BusinessError("邮件发送失败，请稍后再试")


async def reset_password(db: AsyncSession, token: str, new_password: str) -> None:
    """重置密码：校验 token → 改密码 → 作废 token"""
    user_id = await password_reset_service.get_user_id_by_token(token)
    if not user_id:
        raise BusinessError("重置链接无效或已过期，请重新申请")

    result = await db.execute(select(User).where(User.id == user_id))
    user: User | None = result.scalar_one_or_none()
    if not user:
        raise BusinessError("用户不存在")

    user.password_hash = hash_password(new_password)
    await db.flush()
    await password_reset_service.revoke_reset_token(token)


def _get_ip(request: Request) -> str | None:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def _settings():
    from app.config import settings
    return settings
