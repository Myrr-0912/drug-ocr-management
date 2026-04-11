import enum
from sqlalchemy import String, Text, Float, JSON, Integer, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin


class OcrStatus(str, enum.Enum):
    pending = "pending"        # 识别中
    success = "success"        # 识别成功
    failed = "failed"          # 识别失败
    confirmed = "confirmed"    # 已确认入库


class OcrRecord(Base, TimestampMixin):
    """OCR 识别记录表"""
    __tablename__ = "ocr_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    image_path: Mapped[str] = mapped_column(String(500), nullable=False, comment="上传图片路径")
    raw_text: Mapped[str | None] = mapped_column(Text, comment="OCR 原始识别文本")
    extracted_data: Mapped[dict | None] = mapped_column(JSON, comment="结构化提取结果")
    confidence: Mapped[float | None] = mapped_column(Float, comment="识别置信度 0~1")
    status: Mapped[OcrStatus] = mapped_column(
        Enum(OcrStatus), default=OcrStatus.pending, index=True
    )
    # 确认后关联的药品和批次
    drug_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("drugs.id", ondelete="SET NULL"), index=True
    )
    batch_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("drug_batches.id", ondelete="SET NULL")
    )
    operator_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL")
    )
    error_message: Mapped[str | None] = mapped_column(String(500), comment="错误信息")
