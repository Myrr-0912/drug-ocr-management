from typing import Annotated
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RequireLogin, RequirePharmacist
from app.database import get_db
from app.models.user import User
from app.schemas.batch import BatchCreate, BatchUpdate, BatchListQuery
from app.schemas.common import ok
from app.services import batch_service

router = APIRouter(prefix="/batches", tags=["批次管理"])


@router.get("", summary="获取批次列表")
async def list_batches(
    drug_id: int | None = Query(None, description="按药品 ID 过滤"),
    status: str | None = Query(None, description="按状态过滤 (normal/near_expiry/expired)"),
    keyword: str | None = Query(None, description="批号关键词"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = RequireLogin,
):
    query = BatchListQuery(drug_id=drug_id, status=status, keyword=keyword, page=page, page_size=page_size)
    result = await batch_service.list_batches(db, query)
    return ok(result)


@router.post("", summary="新建批次")
async def create_batch(
    data: BatchCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, RequirePharmacist],
):
    batch = await batch_service.create_batch(db, data)
    return ok(batch, "批次创建成功")


@router.get("/{batch_id}", summary="获取批次详情")
async def get_batch(
    batch_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, RequireLogin],
):
    batch, drug_name = await batch_service.get_batch(db, batch_id)
    from app.services.batch_service import _to_response
    return ok(_to_response(batch, drug_name))


@router.put("/{batch_id}", summary="更新批次信息")
async def update_batch(
    batch_id: int,
    data: BatchUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, RequirePharmacist],
):
    batch = await batch_service.update_batch(db, batch_id, data)
    return ok(batch, "更新成功")


@router.delete("/{batch_id}", summary="删除批次")
async def delete_batch(
    batch_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, RequirePharmacist],
):
    await batch_service.delete_batch(db, batch_id)
    return ok(None, "删除成功")
