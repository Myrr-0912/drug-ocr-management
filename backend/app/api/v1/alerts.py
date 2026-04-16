from typing import Annotated
from fastapi import APIRouter, Depends, Query, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RequireLogin, RequirePharmacist, get_current_user
from app.database import get_db, AsyncSessionLocal
from app.models.user import User
from app.schemas.alert import AlertListQuery
from app.schemas.common import ok
from app.services import alert_service

router = APIRouter(prefix="/alerts", tags=["预警管理"])


@router.get("/stats", summary="预警统计概览")
async def get_alert_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, RequireLogin],
):
    """各维度预警计数"""
    stats = await alert_service.get_stats(db)
    return ok(stats)


@router.get("", summary="获取预警列表")
async def list_alerts(
    alert_type: str | None = Query(None, description="预警类型 (expiry_warning/expired/low_stock)"),
    severity: str | None = Query(None, description="严重程度 (info/warning/critical)"),
    is_read: bool | None = Query(None, description="是否已读"),
    is_resolved: bool | None = Query(None, description="是否已解决"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = RequireLogin,
):
    """分页查询预警，支持多维度筛选"""
    # 通过 AlertListQuery 规范化枚举大小写，再解包传递给 service
    q = AlertListQuery(
        alert_type=alert_type,
        severity=severity,
        is_read=is_read,
        is_resolved=is_resolved,
        page=page,
        page_size=page_size,
    )
    total, unread_count, items = await alert_service.get_alerts(
        db,
        alert_type=q.alert_type,
        severity=q.severity,
        is_read=q.is_read,
        is_resolved=q.is_resolved,
        page=q.page,
        page_size=q.page_size,
    )
    return ok({
        "total": total,
        "unread_count": unread_count,
        "items": [
            {
                "id": a.id,
                "alert_type": a.alert_type,
                "drug_id": a.drug_id,
                "batch_id": a.batch_id,
                "message": a.message,
                "severity": a.severity,
                "is_read": a.is_read,
                "is_resolved": a.is_resolved,
                "resolved_by": a.resolved_by,
                "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
                "created_at": a.created_at.isoformat(),
                "updated_at": a.updated_at.isoformat(),
            }
            for a in items
        ],
    })


@router.post("/scan", summary="手动触发预警扫描")
async def manual_scan(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """手动执行一次预警扫描（管理员 / 药师）"""
    if current_user.role not in ("admin", "pharmacist"):
        raise HTTPException(status_code=403, detail="权限不足")
    async with AsyncSessionLocal() as db:
        result = await alert_service.scan_and_create_alerts(db)
    return ok(result, "扫描完成")


@router.patch("/read", summary="批量标记已读")
async def mark_read(
    alert_ids: list[int] = Body(..., description="预警 ID 列表"),
    db: AsyncSession = Depends(get_db),
    _: User = RequireLogin,
):
    count = await alert_service.mark_read(db, alert_ids)
    return ok({"affected": count}, "标记已读成功")


@router.patch("/read-all", summary="全部标记已读")
async def mark_all_read(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, RequireLogin],
):
    count = await alert_service.mark_all_read(db)
    return ok({"affected": count}, "全部已读")


@router.patch("/{alert_id}/resolve", summary="标记预警已解决")
async def resolve_alert(
    alert_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    alert = await alert_service.resolve_alert(db, alert_id, current_user.id)
    if not alert:
        raise HTTPException(status_code=404, detail="预警记录不存在")
    return ok({
        "id": alert.id,
        "is_resolved": alert.is_resolved,
        "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
    }, "已标记解决")
