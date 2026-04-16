from datetime import datetime
from typing import Any
from pydantic import BaseModel, field_validator
from app.models.alert import AlertType, AlertSeverity


class AlertOut(BaseModel):
    """预警记录响应"""
    id: int
    alert_type: AlertType
    drug_id: int | None
    batch_id: int | None
    message: str
    severity: AlertSeverity
    is_read: bool
    is_resolved: bool
    resolved_by: int | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AlertListResponse(BaseModel):
    """预警列表响应"""
    total: int
    unread_count: int
    items: list[AlertOut]


class AlertListQuery(BaseModel):
    """预警列表查询参数"""
    alert_type: AlertType | None = None
    severity: AlertSeverity | None = None
    is_read: bool | None = None
    is_resolved: bool | None = None
    page: int = 1
    page_size: int = 20

    @field_validator("alert_type", "severity", mode="before")
    @classmethod
    def normalize_enum(cls, v: Any) -> Any:
        """将枚举字符串统一转为小写，防止大小写混用导致 422"""
        if isinstance(v, str):
            return v.lower()
        return v


class AlertStats(BaseModel):
    """预警统计概览"""
    total: int
    unread: int
    critical: int
    warning: int
    info: int
    expiry_warning: int
    expired: int
    low_stock: int
