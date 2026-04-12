import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.database import AsyncSessionLocal
from app.services import alert_service

logger = logging.getLogger(__name__)

# 全局调度器实例（在 main.py lifespan 中启动/关闭）
scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")


async def _run_alert_scan() -> None:
    """定时任务：扫描预警（每天 00:05 执行）"""
    logger.info("开始执行预警扫描任务...")
    try:
        async with AsyncSessionLocal() as db:
            result = await alert_service.scan_and_create_alerts(db)
        logger.info(
            "预警扫描完成 — 过期预警: %d, 已过期: %d, 库存不足: %d",
            result["expiry_warning"], result["expired"], result["low_stock"],
        )
    except Exception:
        logger.exception("预警扫描任务执行失败")


def setup_scheduler() -> AsyncIOScheduler:
    """注册所有定时任务并返回调度器"""
    # 每天 00:05 执行一次预警扫描
    scheduler.add_job(
        _run_alert_scan,
        trigger=CronTrigger(hour=0, minute=5),
        id="alert_scan",
        name="每日预警扫描",
        replace_existing=True,
        misfire_grace_time=300,  # 允许 5 分钟内的延迟补偿
    )
    return scheduler
