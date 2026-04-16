from typing import Annotated
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RequireLogin, RequirePharmacist
from app.database import get_db
from app.models.user import User
from app.schemas.common import ok
from app.schemas.drug import DrugCreate, DrugUpdate, DrugListQuery
from app.services import drug_service

router = APIRouter(prefix="/drugs", tags=["药品管理"])


@router.get("", summary="获取药品列表")
async def list_drugs(
    keyword: str | None = Query(None, description="关键词搜索"),
    manufacturer: str | None = Query(None, description="按厂家筛选"),
    category: str | None = Query(None, description="按分类筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = RequireLogin,
):
    query = DrugListQuery(
        keyword=keyword,
        manufacturer=manufacturer,
        category=category,
        page=page,
        page_size=page_size,
    )
    result = await drug_service.list_drugs(db, query)
    return ok(result)


@router.post("", summary="新建药品")
async def create_drug(
    data: DrugCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, RequirePharmacist],
):
    drug = await drug_service.create_drug(db, data, created_by=current_user.id)
    from app.schemas.drug import DrugResponse
    return ok(DrugResponse.model_validate(drug), "药品创建成功")


@router.get("/{drug_id}", summary="获取药品详情")
async def get_drug(
    drug_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, RequireLogin],
):
    drug = await drug_service.get_drug(db, drug_id)
    from app.schemas.drug import DrugResponse
    return ok(DrugResponse.model_validate(drug))


@router.put("/{drug_id}", summary="更新药品信息")
async def update_drug(
    drug_id: int,
    data: DrugUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, RequirePharmacist],
):
    drug = await drug_service.update_drug(db, drug_id, data)
    from app.schemas.drug import DrugResponse
    return ok(DrugResponse.model_validate(drug), "更新成功")


@router.delete("/{drug_id}", summary="删除药品")
async def delete_drug(
    drug_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, RequirePharmacist],
):
    await drug_service.delete_drug(db, drug_id)
    return ok(None, "删除成功")
