import enum
from sqlalchemy import String, Boolean, Integer, Enum, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from app.models.base import Base, TimestampMixin


class AlertType(str, enum.Enum):
    expiry_warning = "expiry_warning"  # 临期预警
    expired = "expired"                # 已过期
    low_stock = "low_stock"            # 库存不足


class AlertSeverity(str, enum.Enum):
    info = "info"          # 提示（90天内过期）
    warning = "warning"    # 警告（30天内过期）
    critical = "critical"  # 严重（已过期/库存归零）


class Alert(Base, TimestampMixin):
    """预警记录表"""
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    alert_type: Mapped[AlertType] = mapped_column(
        Enum(AlertType), nullable=False, index=True
    )
    drug_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("drugs.id", ondelete="CASCADE"), index=True
    )
    batch_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("drug_batches.id", ondelete="CASCADE")
    )
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    severity: Mapped[AlertSeverity] = mapped_column(
        Enum(AlertSeverity), default=AlertSeverity.warning
    )
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL")
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
