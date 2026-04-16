import enum
from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.types import TypeDecorator
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin


class OperationType(str, enum.Enum):
    IN = "in"         # 入库
    OUT = "out"       # 出库
    ADJUST = "adjust" # 盘点调整

    @classmethod
    def _missing_(cls, value: object):
        """大小写容错：'IN'/'in'/'In' 均可正确映射"""
        if isinstance(value, str):
            lower = value.lower()
            for member in cls:
                if member.value == lower:
                    return member
        return None


class _OperationTypeCol(TypeDecorator):
    """
    自定义列类型，完全绕过 SQLAlchemy Enum._object_lookup 的大小写限制。
    - 写入 DB：将 OperationType 枚举存为小写字符串（与现有 DB 数据一致）
    - 读取 DB：大小写容错，统一转为 OperationType 枚举成员
    """
    impl = String(20)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """写入时：枚举 → 小写字符串"""
        if isinstance(value, OperationType):
            return value.value  # 'in' / 'out' / 'adjust'
        if isinstance(value, str):
            return value.lower()
        return value

    def process_result_value(self, value, dialect):
        """读取时：字符串 → OperationType（大小写容错）"""
        if value is None:
            return None
        return OperationType(value.lower())


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
    # 使用自定义 TypeDecorator 绕过 SQLAlchemy Enum 大小写 _object_lookup 问题
    operation_type: Mapped[OperationType] = mapped_column(
        _OperationTypeCol(), nullable=False, comment="操作类型"
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, comment="数量（正数入库/负数出库）")
    operator_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), comment="操作人"
    )
    remark: Mapped[str | None] = mapped_column(String(500), comment="备注")
