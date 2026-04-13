from typing import Annotated
from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RequireLogin
from app.database import get_db
from app.models.user import User
from app.schemas.common import ok
from app.schemas.user import (
    LoginRequest, TokenResponse, UserCreate, UserResponse,
    UserUpdate, ChangePasswordRequest,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["认证"])
_bearer = HTTPBearer()


@router.post("/register", summary="用户注册")
async def register(
    data: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    user = await auth_service.register(db, data)
    return ok(UserResponse.model_validate(user), "注册成功")


@router.post("/login", response_model=None, summary="用户登录")
async def login(
    data: LoginRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    token_resp = await auth_service.login(db, data, request)
    return ok(token_resp, "登录成功")


@router.post("/logout", summary="用户登出（注销 Token）")
async def logout(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    current_user: Annotated[User, RequireLogin],
):
    await auth_service.logout(credentials.credentials)
    return ok(None, "已成功登出")


@router.get("/me", summary="获取当前用户信息")
async def get_me(current_user: Annotated[User, RequireLogin]):
    return ok(UserResponse.model_validate(current_user))


@router.put("/me", summary="更新当前用户信息")
async def update_me(
    data: UserUpdate,
    current_user: Annotated[User, RequireLogin],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if data.real_name is not None:
        current_user.real_name = data.real_name
    if data.phone is not None:
        current_user.phone = data.phone
    if data.email is not None:
        current_user.email = data.email
    await db.flush()
    await db.refresh(current_user)
    return ok(UserResponse.model_validate(current_user), "更新成功")


@router.post("/change-password", summary="修改密码")
async def change_password(
    data: ChangePasswordRequest,
    current_user: Annotated[User, RequireLogin],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await auth_service.change_password(db, current_user, data.old_password, data.new_password)
    return ok(None, "密码修改成功，请重新登录")
