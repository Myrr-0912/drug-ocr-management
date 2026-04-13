from datetime import datetime
from typing import Annotated
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RequireAdmin
from app.database import get_db
from app.models.login_log import LoginLog
from app.models.user import User, UserRole
from app.schemas.common import ok
from app.services import admin_service

router = APIRouter(prefix="/admin", tags=["管理员"])


# ── 请求体 Schema ──────────────────────────────────────────

class AdminCreateUser(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=100)
    real_name: str | None = None
    phone: str | None = None
    email: str | None = None
    role: UserRole = UserRole.user


class AdminUpdateUser(BaseModel):
    real_name: str | None = None
    phone: str | None = None
    email: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=6, max_length=100)


# ── 路由 ───────────────────────────────────────────────────

@router.get("/users", summary="用户列表（管理员）")
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str | None = Query(None, description="按用户名或真实姓名搜索"),
    db: AsyncSession = Depends(get_db),
    _: User = RequireAdmin,
):
    result = await admin_service.list_users(db, page, page_size, keyword)
    return ok(result)


@router.post("/users", summary="创建用户（管理员）")
async def create_user(
    data: AdminCreateUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: User = RequireAdmin,
):
    user = await admin_service.create_user(db, data.model_dump())
    return ok({"id": user.id, "username": user.username}, "用户创建成功")


@router.put("/users/{user_id}", summary="修改用户信息（管理员）")
async def update_user(
    user_id: int,
    data: AdminUpdateUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, RequireAdmin],
):
    payload = {k: v for k, v in data.model_dump().items() if v is not None}
    user = await admin_service.update_user(db, user_id, payload, current_user.id)
    return ok({"id": user.id, "username": user.username, "role": user.role, "is_active": user.is_active}, "更新成功")


@router.delete("/users/{user_id}", summary="删除用户（管理员）")
async def delete_user(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, RequireAdmin],
):
    await admin_service.delete_user(db, user_id, current_user.id)
    return ok(None, "用户已删除")


@router.post("/users/{user_id}/reset-password", summary="重置用户密码（管理员）")
async def reset_password(
    user_id: int,
    data: ResetPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: User = RequireAdmin,
):
    await admin_service.reset_password(db, user_id, data.new_password)
    return ok(None, "密码已重置")


@router.get("/login-logs", summary="登录审计日志（管理员）")
async def list_login_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    username: str | None = Query(None, description="按用户名筛选"),
    success: bool | None = Query(None, description="True=成功 / False=失败"),
    db: AsyncSession = Depends(get_db),
    _: User = RequireAdmin,
):
    """查询登录日志，支持分页 + 按用户名 / 成功/失败筛选"""
    conditions = []
    if username:
        conditions.append(LoginLog.username.ilike(f"%{username}%"))
    if success is not None:
        conditions.append(LoginLog.success == success)

    query = select(LoginLog)
    count_query = select(func.count()).select_from(LoginLog)
    if conditions:
        query = query.where(and_(*conditions))
        count_query = count_query.where(and_(*conditions))

    query = query.order_by(LoginLog.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    total_result = await db.execute(count_query)
    items_result = await db.execute(query)
    total = total_result.scalar_one()
    items = items_result.scalars().all()

    return ok({
        "items": [
            {
                "id": log.id,
                "username": log.username,
                "user_id": log.user_id,
                "ip": log.ip,
                "user_agent": log.user_agent,
                "success": log.success,
                "failure_reason": log.failure_reason,
                "created_at": log.created_at.isoformat(),
            }
            for log in items
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    })
