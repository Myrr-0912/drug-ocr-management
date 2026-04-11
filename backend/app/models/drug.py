from sqlalchemy import String, Text, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class Drug(Base, TimestampMixin):
    """药品基础信息表"""
    __tablename__ = "drugs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True, comment="药品名称")
    common_name: Mapped[str | None] = mapped_column(String(200), comment="通用名")
    approval_number: Mapped[str | None] = mapped_column(
        String(100), unique=True, index=True, comment="批准文号（国药准字）"
    )
    specification: Mapped[str | None] = mapped_column(String(100), comment="规格")
    dosage_form: Mapped[str | None] = mapped_column(String(50), comment="剂型")
    manufacturer: Mapped[str | None] = mapped_column(String(200), index=True, comment="生产企业")
    category: Mapped[str | None] = mapped_column(String(50), comment="分类（处方药/OTC）")
    storage_condition: Mapped[str | None] = mapped_column(String(200), comment="储存条件")
    description: Mapped[str | None] = mapped_column(Text, comment="备注说明")
    image_url: Mapped[str | None] = mapped_column(String(500), comment="药品图片路径")
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), comment="创建人"
    )

    # 关联
    batches: Mapped[list["DrugBatch"]] = relationship(  # noqa: F821
        "DrugBatch", back_populates="drug", lazy="select"
    )
