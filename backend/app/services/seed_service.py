import logging
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import hash_password
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)


async def ensure_initial_admin(db: AsyncSession) -> None:
    """
    首次启动时自动创建管理员账号。

    幂等保证：
      1. 先查 users 表为空再插入；
      2. uvicorn 多 worker 并发启动时，两个 worker 可能同时判定为空，
         第二个插入触发 UNIQUE 冲突 → 捕获 IntegrityError 视为已由他进程种子，正常返回。
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
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        logger.info("初始管理员已由其他启动进程创建，跳过。")
        return
    logger.info("已自动创建初始管理员账号：%s（请在首次登录后立即修改密码）", username)
