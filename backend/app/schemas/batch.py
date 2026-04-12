from datetime import date, datetime
from pydantic import BaseModel, field_validator

from app.models.batch import BatchStatus


class BatchBase(BaseModel):
    drug_id: int
    batch_number: str
    production_date: date | None = None
    expiry_date: date
    quantity: int = 0
    unit: str = "盒"


class BatchCreate(BatchBase):
    @field_validator("batch_number")
    @classmethod
    def batch_number_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("批号不能为空")
        return v.strip()

    @field_validator("quantity")
    @classmethod
    def quantity_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("初始库存量不能为负")
        return v


class BatchUpdate(BaseModel):
    """部分更新，所有字段可选"""
    batch_number: str | None = None
    production_date: date | None = None
    expiry_date: date | None = None
    unit: str | None = None


class BatchResponse(BaseModel):
    id: int
    drug_id: int
    drug_name: str          # 联查药品名
    batch_number: str
    production_date: date | None
    expiry_date: date
    quantity: int
    unit: str
    status: BatchStatus
    source_ocr_id: int | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BatchListQuery(BaseModel):
    """批次列表查询参数"""
    drug_id: int | None = None        # 按药品过滤
    status: BatchStatus | None = None  # 按状态过滤
    keyword: str | None = None        # 批号关键词
    page: int = 1
    page_size: int = 20
