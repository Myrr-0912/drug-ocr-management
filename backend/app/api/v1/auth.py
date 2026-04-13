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
    RefreshTokenRequest, ForgotPasswordRequest, ResetPasswordRequest,
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


@router.post("/logout", summary="用户登出（同时注销 Access + Refresh Token）")
async def logout(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    current_user: Annotated[User, RequireLogin],
    data: RefreshTokenRequest | None = None,
):
    refresh_token = data.refresh_token if data else None
    await auth_service.logout_with_refresh(credentials.credentials, refresh_token)
    return ok(None, "已成功登出")


@router.post("/refresh", summary="使用 Refresh Token 续期（旋转刷新）")
async def refresh_token(
    data: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    token_resp = await auth_service.refresh(db, data.refresh_token)
    return ok(token_resp, "续期成功")


@router.post("/forgot-password", summary="忘记密码（发送重置邮件）")
async def forgot_password(
    data: ForgotPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await auth_service.forgot_password(db, data.email)
    return ok(None, "如果该邮箱已注册，重置邮件将在几分钟内发送")


@router.post("/reset-password", summary="重置密码（凭 token 设置新密码）")
async def reset_password(
    data: ResetPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await auth_service.reset_password(db, data.token, data.new_password)
    return ok(None, "密码重置成功，请使用新密码登录")


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
