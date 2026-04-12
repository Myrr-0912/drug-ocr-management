from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, BusinessError
from app.models.batch import DrugBatch
from app.models.drug import Drug
from app.models.inventory import InventoryRecord, OperationType
from app.models.user import User
from app.schemas.common import PageResponse
from app.schemas.inventory import (
    StockInRequest,
    StockOutRequest,
    AdjustRequest,
    InventoryRecordResponse,
    InventoryListQuery,
)


async def _get_batch(db: AsyncSession, batch_id: int, drug_id: int) -> DrugBatch:
    """验证批次存在且属于指定药品"""
    result = await db.execute(
        select(DrugBatch).where(
            DrugBatch.id == batch_id,
            DrugBatch.drug_id == drug_id,
        )
    )
    batch = result.scalar_one_or_none()
    if not batch:
        raise NotFoundError(f"批次 ID {batch_id} 不存在或不属于药品 ID {drug_id}")
    return batch


async def _to_response(db: AsyncSession, record: InventoryRecord) -> InventoryRecordResponse:
    """将流水 ORM 对象转换为响应 Schema（联查名称）"""
    drug_result = await db.execute(select(Drug).where(Drug.id == record.drug_id))
    drug = drug_result.scalar_one_or_none()

    batch_result = await db.execute(select(DrugBatch).where(DrugBatch.id == record.batch_id))
    batch = batch_result.scalar_one_or_none()

    operator_name: str | None = None
    if record.operator_id:
        op_result = await db.execute(select(User).where(User.id == record.operator_id))
        op = op_result.scalar_one_or_none()
        if op:
            operator_name = op.username

    return InventoryRecordResponse(
        id=record.id,
        drug_id=record.drug_id,
        drug_name=drug.name if drug else "未知药品",
        batch_id=record.batch_id,
        batch_number=batch.batch_number if batch else "未知批次",
        operation_type=record.operation_type,
        quantity=record.quantity,
        operator_id=record.operator_id,
        operator_name=operator_name,
        remark=record.remark,
        created_at=record.created_at,
    )


async def stock_in(db: AsyncSession, data: StockInRequest, operator_id: int) -> InventoryRecordResponse:
    """入库操作：增加批次库存量"""
    batch = await _get_batch(db, data.batch_id, data.drug_id)

    batch.quantity += data.quantity

    record = InventoryRecord(
        drug_id=data.drug_id,
        batch_id=data.batch_id,
        operation_type=OperationType.IN,
        quantity=data.quantity,
        operator_id=operator_id,
        remark=data.remark,
    )
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return await _to_response(db, record)


async def stock_out(db: AsyncSession, data: StockOutRequest, operator_id: int) -> InventoryRecordResponse:
    """出库操作：减少批次库存量"""
    batch = await _get_batch(db, data.batch_id, data.drug_id)

    if batch.quantity < data.quantity:
        raise BusinessError(f"库存不足：当前库存 {batch.quantity} {batch.unit}，出库 {data.quantity} {batch.unit}")

    batch.quantity -= data.quantity

    record = InventoryRecord(
        drug_id=data.drug_id,
        batch_id=data.batch_id,
        operation_type=OperationType.OUT,
        quantity=-data.quantity,  # 出库记录负数
        operator_id=operator_id,
        remark=data.remark,
    )
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return await _to_response(db, record)


async def adjust(db: AsyncSession, data: AdjustRequest, operator_id: int) -> InventoryRecordResponse:
    """盘点调整：将批次库存设置为指定绝对值"""
    batch = await _get_batch(db, data.batch_id, data.drug_id)

    diff = data.new_quantity - batch.quantity
    batch.quantity = data.new_quantity

    record = InventoryRecord(
        drug_id=data.drug_id,
        batch_id=data.batch_id,
        operation_type=OperationType.ADJUST,
        quantity=diff,  # 正数表示盘盈，负数表示盘亏
        operator_id=operator_id,
        remark=data.remark,
    )
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return await _to_response(db, record)


async def list_records(
    db: AsyncSession, query: InventoryListQuery
) -> PageResponse[InventoryRecordResponse]:
    """分页查询库存流水"""
    stmt = select(InventoryRecord)

    if query.drug_id:
        stmt = stmt.where(InventoryRecord.drug_id == query.drug_id)
    if query.batch_id:
        stmt = stmt.where(InventoryRecord.batch_id == query.batch_id)
    if query.operation_type:
        stmt = stmt.where(InventoryRecord.operation_type == query.operation_type)

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()

    stmt = stmt.order_by(InventoryRecord.id.desc()).offset(
        (query.page - 1) * query.page_size
    ).limit(query.page_size)

    result = await db.execute(stmt)
    records = result.scalars().all()

    items = []
    for rec in records:
        items.append(await _to_response(db, rec))

    return PageResponse(items=items, total=total, page=query.page, page_size=query.page_size)
