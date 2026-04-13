from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RequireLogin
from app.database import get_db
from app.schemas.common import ok
from app.services import stats_service

router = APIRouter(prefix="/stats", tags=["统计分析"])


@router.get("/overview", summary="仪表盘概览统计")
async def overview(
    db: AsyncSession = Depends(get_db),
    _=RequireLogin,
):
    data = await stats_service.get_overview(db)
    return ok(data)


@router.get("/inventory-trend", summary="近 N 天出入库趋势")
async def inventory_trend(
    days: int = Query(30, ge=7, le=90, description="统计天数"),
    db: AsyncSession = Depends(get_db),
    _=RequireLogin,
):
    data = await stats_service.get_inventory_trend(db, days)
    return ok(data)


@router.get("/expiry-distribution", summary="批次过期分布统计")
async def expiry_distribution(
    db: AsyncSession = Depends(get_db),
    _=RequireLogin,
):
    data = await stats_service.get_expiry_distribution(db)
    return ok(data)
