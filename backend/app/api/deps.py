from typing import Annotated
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UnauthorizedError, ForbiddenError
from app.core.security import decode_access_token
from app.database import get_db
from app.models.user import User, UserRole

# Bearer Token 提取器
_bearer = HTTPBearer()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """依赖注入：解析 JWT 并返回当前登录用户"""
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise UnauthorizedError("Token 无效或已过期")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise UnauthorizedError("用户不存在或已被禁用")
    return user


def require_roles(*roles: UserRole):
    """角色权限依赖工厂"""
    async def _checker(current_user: Annotated[User, Depends(get_current_user)]) -> User:
        if current_user.role not in roles:
            raise ForbiddenError(f"需要角色：{[r.value for r in roles]}")
        return current_user
    return _checker


# 常用权限组合
RequireAdmin = Depends(require_roles(UserRole.admin))
RequirePharmacist = Depends(require_roles(UserRole.admin, UserRole.pharmacist))
RequireLogin = Depends(get_current_user)
