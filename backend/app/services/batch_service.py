from datetime import date
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ConflictError, BusinessError
from app.models.batch import DrugBatch, BatchStatus
from app.models.drug import Drug
from app.schemas.batch import BatchCreate, BatchUpdate, BatchListQuery, BatchResponse
from app.schemas.common import PageResponse


async def _get_drug_name(db: AsyncSession, drug_id: int) -> str:
    """获取药品名称，找不到则抛出异常"""
    result = await db.execute(select(Drug).where(Drug.id == drug_id))
    drug = result.scalar_one_or_none()
    if not drug:
        raise NotFoundError(f"药品 ID {drug_id} 不存在")
    return drug.name


def _compute_status(expiry_date: date) -> BatchStatus:
    """根据有效期计算批次状态"""
    today = date.today()
    delta = (expiry_date - today).days
    if delta < 0:
        return BatchStatus.expired
    elif delta <= 30:
        return BatchStatus.near_expiry
    return BatchStatus.normal


def _to_response(batch: DrugBatch, drug_name: str) -> BatchResponse:
    """将 ORM 对象转换为响应 Schema"""
    return BatchResponse(
        id=batch.id,
        drug_id=batch.drug_id,
        drug_name=drug_name,
        batch_number=batch.batch_number,
        production_date=batch.production_date,
        expiry_date=batch.expiry_date,
        quantity=batch.quantity,
        unit=batch.unit,
        status=batch.status,
        source_ocr_id=batch.source_ocr_id,
        created_at=batch.created_at,
        updated_at=batch.updated_at,
    )


async def create_batch(db: AsyncSession, data: BatchCreate, source_ocr_id: int | None = None) -> BatchResponse:
    """新建药品批次"""
    drug_name = await _get_drug_name(db, data.drug_id)

    # 同一药品的批号唯一性校验
    exists = await db.execute(
        select(DrugBatch).where(
            DrugBatch.drug_id == data.drug_id,
            DrugBatch.batch_number == data.batch_number,
        )
    )
    if exists.scalar_one_or_none():
        raise ConflictError(f"药品 ID {data.drug_id} 下批号 '{data.batch_number}' 已存在")

    status = _compute_status(data.expiry_date)
    batch = DrugBatch(
        drug_id=data.drug_id,
        batch_number=data.batch_number,
        production_date=data.production_date,
        expiry_date=data.expiry_date,
        quantity=data.quantity,
        unit=data.unit,
        status=status,
        source_ocr_id=source_ocr_id,
    )
    db.add(batch)
    await db.flush()
    await db.refresh(batch)
    return _to_response(batch, drug_name)


async def get_batch(db: AsyncSession, batch_id: int) -> tuple[DrugBatch, str]:
    """根据 ID 获取批次，返回 (batch, drug_name)"""
    result = await db.execute(
        select(DrugBatch, Drug.name)
        .join(Drug, Drug.id == DrugBatch.drug_id)
        .where(DrugBatch.id == batch_id)
    )
    row = result.one_or_none()
    if not row:
        raise NotFoundError(f"批次 ID {batch_id} 不存在")
    return row[0], row[1]


async def update_batch(db: AsyncSession, batch_id: int, data: BatchUpdate) -> BatchResponse:
    """更新批次信息"""
    batch, drug_name = await get_batch(db, batch_id)

    update_data = data.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(batch, field, value)

    # 有效期变更时重新计算状态
    if "expiry_date" in update_data:
        batch.status = _compute_status(batch.expiry_date)

    await db.flush()
    await db.refresh(batch)
    return _to_response(batch, drug_name)


async def delete_batch(db: AsyncSession, batch_id: int) -> None:
    """删除批次（仅允许库存为 0 的批次）"""
    batch, _ = await get_batch(db, batch_id)
    if batch.quantity != 0:
        raise BusinessError(f"批次库存量为 {batch.quantity}，不能删除非零库存批次")
    await db.delete(batch)
    await db.flush()


async def list_batches(db: AsyncSession, query: BatchListQuery) -> PageResponse[BatchResponse]:
    """分页查询批次列表"""
    stmt = (
        select(DrugBatch, Drug.name)
        .join(Drug, Drug.id == DrugBatch.drug_id)
    )

    if query.drug_id:
        stmt = stmt.where(DrugBatch.drug_id == query.drug_id)
    if query.status:
        stmt = stmt.where(DrugBatch.status == query.status)
    if query.keyword:
        stmt = stmt.where(DrugBatch.batch_number.like(f"%{query.keyword}%"))

    # 统计总数
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    # 分页，最新优先
    stmt = stmt.order_by(DrugBatch.id.desc()).offset(
        (query.page - 1) * query.page_size
    ).limit(query.page_size)

    result = await db.execute(stmt)
    items = [_to_response(row[0], row[1]) for row in result.all()]

    return PageResponse(items=items, total=total, page=query.page, page_size=query.page_size)
