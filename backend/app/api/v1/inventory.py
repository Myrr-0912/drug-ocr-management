from typing import Annotated
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RequireLogin, RequirePharmacist
from app.database import get_db
from app.models.inventory import OperationType
from app.models.user import User
from app.schemas.common import ok
from app.schemas.inventory import AdjustRequest, StockInRequest, StockOutRequest, InventoryListQuery
from app.services import inventory_service

router = APIRouter(prefix="/inventory", tags=["库存管理"])


@router.get("", summary="获取库存流水记录")
async def list_records(
    drug_id: int | None = Query(None, description="按药品过滤"),
    batch_id: int | None = Query(None, description="按批次过滤"),
    operation_type: OperationType | None = Query(None, description="按操作类型过滤"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = RequireLogin,
):
    query = InventoryListQuery(
        drug_id=drug_id,
        batch_id=batch_id,
        operation_type=operation_type,
        page=page,
        page_size=page_size,
    )
    result = await inventory_service.list_records(db, query)
    return ok(result)


@router.post("/stock-in", summary="入库操作")
async def stock_in(
    data: StockInRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, RequirePharmacist],
):
    record = await inventory_service.stock_in(db, data, operator_id=current_user.id)
    return ok(record, "入库成功")


@router.post("/stock-out", summary="出库操作")
async def stock_out(
    data: StockOutRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, RequirePharmacist],
):
    record = await inventory_service.stock_out(db, data, operator_id=current_user.id)
    return ok(record, "出库成功")


@router.post("/adjust", summary="盘点调整")
async def adjust(
    data: AdjustRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, RequirePharmacist],
):
    record = await inventory_service.adjust(db, data, operator_id=current_user.id)
    return ok(record, "盘点调整成功")
