from datetime import datetime
from pydantic import BaseModel, field_validator


class DrugBase(BaseModel):
    name: str
    common_name: str | None = None
    approval_number: str | None = None
    specification: str | None = None
    dosage_form: str | None = None
    manufacturer: str | None = None
    category: str | None = None
    storage_condition: str | None = None
    description: str | None = None


class DrugCreate(DrugBase):
    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("药品名称不能为空")
        return v.strip()


class DrugUpdate(BaseModel):
    """部分更新，所有字段可选"""
    name: str | None = None
    common_name: str | None = None
    approval_number: str | None = None
    specification: str | None = None
    dosage_form: str | None = None
    manufacturer: str | None = None
    category: str | None = None
    storage_condition: str | None = None
    description: str | None = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("药品名称不能为空")
        return v.strip() if v else v


class DrugResponse(DrugBase):
    id: int
    image_url: str | None = None
    created_by: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DrugListQuery(BaseModel):
    """药品列表查询参数"""
    keyword: str | None = None       # 搜索关键词（名称/通用名/批准文号）
    manufacturer: str | None = None  # 按厂家筛选
    category: str | None = None      # 按分类筛选
    page: int = 1
    page_size: int = 20
