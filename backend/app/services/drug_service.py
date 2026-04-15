from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ConflictError
from app.models.drug import Drug
from app.models.batch import DrugBatch
from app.schemas.common import PageResponse
from app.schemas.drug import DrugCreate, DrugUpdate, DrugListQuery, DrugResponse


async def create_drug(db: AsyncSession, data: DrugCreate, created_by: int) -> Drug:
    """新建药品"""
    # 批准文号唯一性检查
    if data.approval_number:
        exists = await db.execute(
            select(Drug).where(Drug.approval_number == data.approval_number)
        )
        if exists.scalar_one_or_none():
            raise ConflictError(f"批准文号 '{data.approval_number}' 已存在")

    drug = Drug(**data.model_dump(), created_by=created_by)
    db.add(drug)
    await db.flush()
    await db.refresh(drug)
    return drug


async def get_drug(db: AsyncSession, drug_id: int) -> Drug:
    """根据 ID 获取药品"""
    result = await db.execute(select(Drug).where(Drug.id == drug_id))
    drug = result.scalar_one_or_none()
    if not drug:
        raise NotFoundError(f"药品 ID {drug_id} 不存在")
    return drug


async def update_drug(db: AsyncSession, drug_id: int, data: DrugUpdate) -> Drug:
    """更新药品信息"""
    drug = await get_drug(db, drug_id)

    # 批准文号唯一性检查（排除自身）
    if data.approval_number and data.approval_number != drug.approval_number:
        exists = await db.execute(
            select(Drug).where(
                Drug.approval_number == data.approval_number,
                Drug.id != drug_id,
            )
        )
        if exists.scalar_one_or_none():
            raise ConflictError(f"批准文号 '{data.approval_number}' 已存在")

    # 只更新传入的非 None 字段
    update_data = data.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(drug, field, value)

    await db.flush()
    await db.refresh(drug)
    return drug


async def delete_drug(db: AsyncSession, drug_id: int) -> None:
    """删除药品（有关联批次时拒绝删除）"""
    drug = await get_drug(db, drug_id)

    # 检查是否存在关联批次，RESTRICT 约束下不可强删
    batch_count_result = await db.execute(
        select(func.count()).where(DrugBatch.drug_id == drug_id)
    )
    batch_count = batch_count_result.scalar_one()
    if batch_count > 0:
        raise ConflictError(f"该药品下存在 {batch_count} 条批次记录，请先删除相关批次后再删除药品")

    await db.delete(drug)
    await db.flush()


async def list_drugs(
    db: AsyncSession, query: DrugListQuery
) -> PageResponse[DrugResponse]:
    """分页查询药品列表"""
    stmt = select(Drug)

    # 关键词搜索
    if query.keyword:
        kw = f"%{query.keyword}%"
        stmt = stmt.where(
            or_(
                Drug.name.like(kw),
                Drug.common_name.like(kw),
                Drug.approval_number.like(kw),
            )
        )
    if query.manufacturer:
        stmt = stmt.where(Drug.manufacturer.like(f"%{query.manufacturer}%"))
    if query.category:
        stmt = stmt.where(Drug.category == query.category)

    # 总数
    count_result = await db.execute(select(func.count()).select_from(stmt.subquery()))
    total = count_result.scalar_one()

    # 分页
    stmt = stmt.order_by(Drug.id.desc()).offset(
        (query.page - 1) * query.page_size
    ).limit(query.page_size)

    result = await db.execute(stmt)
    items = [DrugResponse.model_validate(r) for r in result.scalars().all()]

    return PageResponse(
        items=items,
        total=total,
        page=query.page,
        page_size=query.page_size,
    )
