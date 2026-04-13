from datetime import datetime
from pydantic import BaseModel
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
