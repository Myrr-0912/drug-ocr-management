from datetime import datetime
from sqlalchemy import String, Boolean, Integer, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class LoginLog(Base):
    """登录审计日志表"""
    __tablename__ = "login_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 登录的用户名（即便用户不存在也记录）
    username: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # 登录成功时关联的用户 ID，失败或用户不存在时为 NULL
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 客户端 IP 地址
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    # 客户端 User-Agent
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 是否登录成功
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)
    # 失败原因（成功时为 NULL）
    failure_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False, index=True
    )
