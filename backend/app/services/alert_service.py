from datetime import date, datetime
from sqlalchemy import select, func, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert, AlertType, AlertSeverity
from app.models.batch import DrugBatch, BatchStatus
from app.models.drug import Drug
from app.config import settings


# ───────────────────────────── 扫描逻辑 ─────────────────────────────

async def scan_and_create_alerts(db: AsyncSession) -> dict[str, int]:
    """
    扫描所有批次，按过期状态和库存生成预警。
    - 已过期：critical
    - 30 天内过期（expiry_warning_days）：warning
    - 90 天内过期：info
    - 库存 <= low_stock_threshold：critical/warning
    返回各类生成数量的汇总。
    """
    today = date.today()
    warn_days = settings.expiry_warning_days       # 默认 30 天
    info_days = 90                                  # 信息级别：90 天内

    # 一次性拉取所有未过期 + 临期批次（quantity > 0 或已过期）
    stmt = (
        select(DrugBatch, Drug.name.label("drug_name"))
        .join(Drug, DrugBatch.drug_id == Drug.id)
        .where(Drug.is_active.is_(True))
    )
    rows = (await db.execute(stmt)).all()

    created = {"expiry_warning": 0, "expired": 0, "low_stock": 0}

    for batch, drug_name in rows:
        days_left = (batch.expiry_date - today).days

        # —— 过期预警 ——
        if days_left < 0:
            # 已过期
            await _upsert_alert(
                db,
                alert_type=AlertType.expired,
                drug_id=batch.drug_id,
                batch_id=batch.id,
                severity=AlertSeverity.critical,
                message=f"【{drug_name}】批次 {batch.batch_number} 已过期"
                        f"（过期 {-days_left} 天）",
            )
            created["expired"] += 1
            # 同步更新批次状态
            await db.execute(
                update(DrugBatch)
                .where(DrugBatch.id == batch.id)
                .values(status=BatchStatus.expired)
            )
        elif days_left <= warn_days:
            # 30 天内过期 → warning
            await _upsert_alert(
                db,
                alert_type=AlertType.expiry_warning,
                drug_id=batch.drug_id,
                batch_id=batch.id,
                severity=AlertSeverity.warning,
                message=f"【{drug_name}】批次 {batch.batch_number} 将于 {days_left} 天后过期"
                        f"（{batch.expiry_date}）",
            )
            created["expiry_warning"] += 1
            await db.execute(
                update(DrugBatch)
                .where(DrugBatch.id == batch.id)
                .values(status=BatchStatus.near_expiry)
            )
        elif days_left <= info_days:
            # 90 天内过期 → info
            await _upsert_alert(
                db,
                alert_type=AlertType.expiry_warning,
                drug_id=batch.drug_id,
                batch_id=batch.id,
                severity=AlertSeverity.info,
                message=f"【{drug_name}】批次 {batch.batch_number} 将于 {days_left} 天后过期"
                        f"（{batch.expiry_date}）",
            )
            created["expiry_warning"] += 1
        else:
            # 状态恢复正常
            await db.execute(
                update(DrugBatch)
                .where(DrugBatch.id == batch.id)
                .values(status=BatchStatus.normal)
            )

        # —— 库存不足预警 ——
        threshold = settings.low_stock_threshold
        if batch.quantity <= 0:
            await _upsert_alert(
                db,
                alert_type=AlertType.low_stock,
                drug_id=batch.drug_id,
                batch_id=batch.id,
                severity=AlertSeverity.critical,
                message=f"【{drug_name}】批次 {batch.batch_number} 库存已清零",
            )
            created["low_stock"] += 1
        elif batch.quantity <= threshold:
            await _upsert_alert(
                db,
                alert_type=AlertType.low_stock,
                drug_id=batch.drug_id,
                batch_id=batch.id,
                severity=AlertSeverity.warning,
                message=f"【{drug_name}】批次 {batch.batch_number} 库存不足"
                        f"（剩余 {batch.quantity} {batch.unit}，阈值 {threshold}）",
            )
            created["low_stock"] += 1

    await db.commit()
    return created


async def _upsert_alert(
    db: AsyncSession,
    alert_type: AlertType,
    drug_id: int | None,
    batch_id: int | None,
    severity: AlertSeverity,
    message: str,
) -> None:
    """
    同一批次同一类型预警去重：已存在且未解决则仅更新 message；
    否则新建。
    """
    existing = await db.execute(
        select(Alert).where(
            and_(
                Alert.alert_type == alert_type,
                Alert.batch_id == batch_id,
                Alert.is_resolved.is_(False),
            )
        )
    )
    alert = existing.scalar_one_or_none()
    if alert:
        alert.message = message
        alert.severity = severity
    else:
        db.add(Alert(
            alert_type=alert_type,
            drug_id=drug_id,
            batch_id=batch_id,
            severity=severity,
            message=message,
        ))


# ───────────────────────────── 查询接口 ─────────────────────────────

async def get_alerts(
    db: AsyncSession,
    *,
    alert_type: AlertType | None = None,
    severity: AlertSeverity | None = None,
    is_read: bool | None = None,
    is_resolved: bool | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[int, int, list[Alert]]:
    """
    分页查询预警列表，返回 (total, unread_count, items)。
    """
    filters = []
    if alert_type:
        filters.append(Alert.alert_type == alert_type)
    if severity:
        filters.append(Alert.severity == severity)
    if is_read is not None:
        filters.append(Alert.is_read.is_(is_read))
    if is_resolved is not None:
        filters.append(Alert.is_resolved.is_(is_resolved))

    where = and_(*filters) if filters else True

    total_r = await db.execute(select(func.count()).select_from(Alert).where(where))
    total: int = total_r.scalar_one()

    unread_r = await db.execute(
        select(func.count()).select_from(Alert).where(Alert.is_read.is_(False))
    )
    unread_count: int = unread_r.scalar_one()

    items_r = await db.execute(
        select(Alert)
        .where(where)
        .order_by(Alert.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = list(items_r.scalars().all())

    return total, unread_count, items


async def get_stats(db: AsyncSession) -> dict:
    """预警统计：各维度计数"""
    rows = await db.execute(
        select(
            func.count().label("total"),
            func.sum(func.if_(Alert.is_read.is_(False), 1, 0)).label("unread"),
            func.sum(func.if_(Alert.severity == AlertSeverity.critical, 1, 0)).label("critical"),
            func.sum(func.if_(Alert.severity == AlertSeverity.warning, 1, 0)).label("warning"),
            func.sum(func.if_(Alert.severity == AlertSeverity.info, 1, 0)).label("info"),
            func.sum(func.if_(Alert.alert_type == AlertType.expiry_warning, 1, 0)).label("expiry_warning"),
            func.sum(func.if_(Alert.alert_type == AlertType.expired, 1, 0)).label("expired"),
            func.sum(func.if_(Alert.alert_type == AlertType.low_stock, 1, 0)).label("low_stock"),
        )
    )
    row = rows.one()
    return {
        "total": row.total or 0,
        "unread": row.unread or 0,
        "critical": row.critical or 0,
        "warning": row.warning or 0,
        "info": row.info or 0,
        "expiry_warning": row.expiry_warning or 0,
        "expired": row.expired or 0,
        "low_stock": row.low_stock or 0,
    }


async def mark_read(db: AsyncSession, alert_ids: list[int]) -> int:
    """批量标记已读，返回影响行数"""
    result = await db.execute(
        update(Alert)
        .where(Alert.id.in_(alert_ids))
        .values(is_read=True)
    )
    await db.commit()
    return result.rowcount


async def mark_all_read(db: AsyncSession) -> int:
    """全部标记已读"""
    result = await db.execute(
        update(Alert).where(Alert.is_read.is_(False)).values(is_read=True)
    )
    await db.commit()
    return result.rowcount


async def resolve_alert(db: AsyncSession, alert_id: int, user_id: int) -> Alert | None:
    """标记单条预警为已解决"""
    r = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = r.scalar_one_or_none()
    if not alert:
        return None
    alert.is_resolved = True
    alert.resolved_by = user_id
    alert.resolved_at = datetime.utcnow()
    alert.is_read = True
    await db.commit()
    await db.refresh(alert)
    return alert
