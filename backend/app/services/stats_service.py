from datetime import date, timedelta
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.drug import Drug
from app.models.batch import DrugBatch, BatchStatus
from app.models.inventory import InventoryRecord, OperationType
from app.models.alert import Alert


async def get_overview(db: AsyncSession) -> dict:
    """获取仪表盘概览统计数据"""
    today = date.today()
    today_start = today  # SQLAlchemy Date 比较直接用 date

    # 药品总数
    total_drugs = await db.scalar(select(func.count()).select_from(Drug))

    # 批次总数（有效库存批次，quantity > 0）
    total_batches = await db.scalar(
        select(func.count()).select_from(DrugBatch).where(DrugBatch.quantity > 0)
    )

    # 活跃预警数（未处理）
    active_alerts = await db.scalar(
        select(func.count()).select_from(Alert).where(Alert.is_resolved == False)  # noqa: E712
    )

    # 今日入库笔数
    today_stock_in = await db.scalar(
        select(func.count()).select_from(InventoryRecord).where(
            InventoryRecord.operation_type == OperationType.IN,
            func.date(InventoryRecord.created_at) == today_start,
        )
    )

    return {
        "total_drugs": total_drugs or 0,
        "total_batches": total_batches or 0,
        "active_alerts": active_alerts or 0,
        "today_stock_in": today_stock_in or 0,
    }


async def get_inventory_trend(db: AsyncSession, days: int = 30) -> list[dict]:
    """获取近 N 天的出入库趋势，按日分组"""
    start_date = date.today() - timedelta(days=days - 1)

    # 查询每天的入库/出库汇总
    rows = await db.execute(
        select(
            func.date(InventoryRecord.created_at).label("day"),
            func.sum(
                case((InventoryRecord.operation_type == OperationType.IN, InventoryRecord.quantity), else_=0)
            ).label("stock_in"),
            func.sum(
                case((InventoryRecord.operation_type == OperationType.OUT, func.abs(InventoryRecord.quantity)), else_=0)
            ).label("stock_out"),
        )
        .where(func.date(InventoryRecord.created_at) >= start_date)
        .group_by(func.date(InventoryRecord.created_at))
        .order_by(func.date(InventoryRecord.created_at))
    )
    db_rows = {str(r.day): {"stock_in": int(r.stock_in or 0), "stock_out": int(r.stock_out or 0)} for r in rows}

    # 补全所有日期（无数据的天填 0）
    result = []
    for i in range(days):
        d = (start_date + timedelta(days=i)).isoformat()
        data = db_rows.get(d, {"stock_in": 0, "stock_out": 0})
        result.append({"date": d, **data})

    return result


async def get_expiry_distribution(db: AsyncSession) -> dict:
    """获取批次过期分布（有效库存批次）"""
    today = date.today()
    near_30 = today + timedelta(days=30)
    near_90 = today + timedelta(days=90)

    rows = await db.execute(
        select(
            func.sum(case((DrugBatch.expiry_date < today, 1), else_=0)).label("expired"),
            func.sum(case(
                (DrugBatch.expiry_date >= today, case(
                    (DrugBatch.expiry_date <= near_30, 1), else_=0
                )),
                else_=0,
            )).label("near_30"),
            func.sum(case(
                (DrugBatch.expiry_date > near_30, case(
                    (DrugBatch.expiry_date <= near_90, 1), else_=0
                )),
                else_=0,
            )).label("near_90"),
            func.sum(case((DrugBatch.expiry_date > near_90, 1), else_=0)).label("normal"),
        )
        .where(DrugBatch.quantity > 0)
    )
    row = rows.one()
    return {
        "expired": int(row.expired or 0),
        "near_30": int(row.near_30 or 0),
        "near_90": int(row.near_90 or 0),
        "normal": int(row.normal or 0),
    }
