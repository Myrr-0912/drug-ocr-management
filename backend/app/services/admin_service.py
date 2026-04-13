from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ConflictError, ForbiddenError
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.schemas.user import UserResponse


async def list_users(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
) -> dict:
    """分页查询用户列表，支持关键词搜索"""
    stmt = select(User)
    count_stmt = select(func.count()).select_from(User)

    if keyword:
        like = f"%{keyword}%"
        condition = or_(User.username.ilike(like), User.real_name.ilike(like))
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)

    total = await db.scalar(count_stmt) or 0
    stmt = stmt.order_by(User.id.asc()).offset((page - 1) * page_size).limit(page_size)
    rows = await db.execute(stmt)
    users = rows.scalars().all()

    return {
        "items": [UserResponse.model_validate(u) for u in users],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


async def create_user(db: AsyncSession, data: dict) -> User:
    """管理员创建用户（可指定角色）"""
    exist = await db.scalar(select(User).where(User.username == data["username"]))
    if exist:
        raise ConflictError(f"用户名 '{data['username']}' 已存在")

    user = User(
        username=data["username"],
        password_hash=hash_password(data["password"]),
        real_name=data.get("real_name"),
        phone=data.get("phone"),
        email=data.get("email"),
        role=UserRole(data.get("role", UserRole.user)),
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def update_user(db: AsyncSession, user_id: int, data: dict, current_user_id: int) -> User:
    """修改用户信息（角色、激活状态、真实姓名等）"""
    user = await db.get(User, user_id)
    if not user:
        raise NotFoundError("用户不存在")

    # 不允许修改自己的角色或激活状态
    if user_id == current_user_id and ("role" in data or "is_active" in data):
        raise ForbiddenError("不能修改自己的角色或账号状态")

    if "role" in data:
        user.role = UserRole(data["role"])
    if "is_active" in data:
        user.is_active = data["is_active"]
    if "real_name" in data:
        user.real_name = data["real_name"]
    if "email" in data:
        user.email = data["email"]
    if "phone" in data:
        user.phone = data["phone"]

    await db.flush()
    await db.refresh(user)
    return user


async def delete_user(db: AsyncSession, user_id: int, current_user_id: int) -> None:
    """删除用户（不能删除自己）"""
    if user_id == current_user_id:
        raise ForbiddenError("不能删除自己的账号")

    user = await db.get(User, user_id)
    if not user:
        raise NotFoundError("用户不存在")

    await db.delete(user)
    await db.flush()


async def reset_password(db: AsyncSession, user_id: int, new_password: str) -> None:
    """重置用户密码"""
    user = await db.get(User, user_id)
    if not user:
        raise NotFoundError("用户不存在")

    user.password_hash = hash_password(new_password)
    await db.flush()
