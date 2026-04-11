import enum
from sqlalchemy import String, Integer, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin


class OperationType(str, enum.Enum):
    IN = "in"        # 入库
    OUT = "out"      # 出库
    ADJUST = "adjust"  # 盘点调整


class InventoryRecord(Base, TimestampMixin):
    """库存流水记录表"""
    __tablename__ = "inventory_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    drug_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("drugs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    batch_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("drug_batches.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    operation_type: Mapped[OperationType] = mapped_column(
        Enum(OperationType), nullable=False, comment="操作类型"
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, comment="数量（正数入库/负数出库）")
    operator_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), comment="操作人"
    )
    remark: Mapped[str | None] = mapped_column(String(500), comment="备注")
