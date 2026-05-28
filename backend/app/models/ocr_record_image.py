from sqlalchemy import Enum, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.ocr_record import OcrStatus


class OcrRecordImage(Base, TimestampMixin):
    """OCR 多图上传的单张图片识别证据表"""
    __tablename__ = "ocr_record_images"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ocr_record_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ocr_records.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="所属 OCR 主记录",
    )
    image_path: Mapped[str] = mapped_column(String(500), nullable=False, comment="上传图片路径")
    image_index: Mapped[int] = mapped_column(Integer, nullable=False, comment="上传顺序，从 1 开始")
    raw_text: Mapped[str | None] = mapped_column(Text, comment="单图 OCR 原始识别文本")
    extracted_data: Mapped[dict | None] = mapped_column(JSON, comment="单图结构化提取结果")
    confidence: Mapped[float | None] = mapped_column(Float, comment="单图字段完整度 0~1")
    status: Mapped[OcrStatus] = mapped_column(
        Enum(OcrStatus),
        default=OcrStatus.pending,
        index=True,
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(String(500), comment="单图错误信息")

    record: Mapped["OcrRecord"] = relationship("OcrRecord", back_populates="images")
