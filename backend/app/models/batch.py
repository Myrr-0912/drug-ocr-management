import enum
from datetime import date
from sqlalchemy import String, Integer, Date, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class BatchStatus(str, enum.Enum):
    normal = "normal"          # 正常
    near_expiry = "near_expiry"  # 临期（30天内）
    expired = "expired"        # 已过期


class DrugBatch(Base, TimestampMixin):
    """药品批次表"""
    __tablename__ = "drug_batches"
    __table_args__ = (
        # 同一药品的批号唯一
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    drug_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("drugs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    batch_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True, comment="批号")
    production_date: Mapped[date | None] = mapped_column(Date, comment="生产日期")
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False, index=True, comment="有效期至")
    quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="当前库存量")
    unit: Mapped[str] = mapped_column(String(20), default="盒", comment="单位")
    status: Mapped[BatchStatus] = mapped_column(
        Enum(BatchStatus), default=BatchStatus.normal, comment="状态"
    )
    source_ocr_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("ocr_records.id", ondelete="SET NULL"), comment="来源 OCR 记录"
    )

    # 关联
    drug: Mapped["Drug"] = relationship("Drug", back_populates="batches")  # noqa: F821
