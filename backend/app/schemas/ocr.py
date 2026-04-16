from datetime import date, datetime
from typing import Any
from pydantic import BaseModel, field_validator

from app.models.ocr_record import OcrStatus


class ExtractedDrugData(BaseModel):
    """OCR 提取的结构化药品信息"""
    name: str | None = None             # 药品名称
    approval_number: str | None = None  # 批准文号
    manufacturer: str | None = None     # 生产厂家
    specification: str | None = None    # 规格
    batch_number: str | None = None     # 批号
    production_date: str | None = None  # 生产日期（原始字符串）
    expiry_date: str | None = None      # 有效期（原始字符串）
    quantity: int | None = None         # 数量


class OcrRecordResponse(BaseModel):
    id: int
    image_path: str
    raw_text: str | None = None
    extracted_data: dict | None = None
    confidence: float | None = None
    status: OcrStatus
    drug_id: int | None = None
    batch_id: int | None = None
    error_message: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class OcrConfirmRequest(BaseModel):
    """用户编辑并确认识别结果，触发入库"""
    # 药品信息：drug_id 有值则关联已有药品；否则创建新药品
    drug_id: int | None = None
    drug_name: str
    approval_number: str | None = None
    manufacturer: str | None = None
    specification: str | None = None

    # 批次信息
    batch_number: str
    production_date: date | None = None
    expiry_date: date
    quantity: int = 0
    unit: str = "盒"

    @field_validator("drug_name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("药品名称不能为空")
        return v.strip()

    @field_validator("batch_number")
    @classmethod
    def batch_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("批号不能为空")
        return v.strip()


class OcrConfirmResponse(BaseModel):
    """确认入库后返回结果"""
    ocr_id: int
    drug_id: int
    batch_id: int
    message: str = "识别结果已确认入库"


class OcrListQuery(BaseModel):
    """OCR 记录列表查询参数"""
    status: OcrStatus | None = None
    page: int = 1
    page_size: int = 20

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, v: Any) -> Any:
        """将状态字符串统一转为小写，防止大小写混用导致 422"""
        if isinstance(v, str):
            return v.lower()
        return v
