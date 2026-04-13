import logging
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import hash_password
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)


async def ensure_initial_admin(db: AsyncSession) -> None:
    """
    首次启动时自动创建管理员账号。
    仅在 users 表完全为空时执行，非空则跳过（幂等）。
    """
    result = await db.execute(select(func.count()).select_from(User))
    count = result.scalar_one()
    if count > 0:
        return

    username = settings.initial_admin_username
    admin = User(
        username=username,
        password_hash=hash_password(settings.initial_admin_password),
        real_name=settings.initial_admin_real_name,
        role=UserRole.admin,
        is_active=True,
    )
    db.add(admin)
    await db.commit()
    logger.info("已自动创建初始管理员账号：%s（请在首次登录后立即修改密码）", username)
