from datetime import datetime
from pydantic import BaseModel, field_validator

from app.models.inventory import OperationType


class StockInRequest(BaseModel):
    """入库请求"""
    drug_id: int
    batch_id: int
    quantity: int
    remark: str | None = None

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("入库数量必须大于 0")
        return v


class StockOutRequest(BaseModel):
    """出库请求"""
    drug_id: int
    batch_id: int
    quantity: int
    remark: str | None = None

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("出库数量必须大于 0")
        return v


class AdjustRequest(BaseModel):
    """盘点调整请求（设置绝对库存量）"""
    drug_id: int
    batch_id: int
    new_quantity: int
    remark: str | None = None

    @field_validator("new_quantity")
    @classmethod
    def quantity_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("调整后库存量不能为负")
        return v


class InventoryRecordResponse(BaseModel):
    id: int
    drug_id: int
    drug_name: str          # 联查药品名
    batch_id: int
    batch_number: str       # 联查批号
    operation_type: OperationType
    quantity: int
    operator_id: int | None
    operator_name: str | None  # 联查操作人
    remark: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class InventoryListQuery(BaseModel):
    """库存流水查询参数"""
    drug_id: int | None = None
    batch_id: int | None = None
    operation_type: OperationType | None = None
    page: int = 1
    page_size: int = 20
