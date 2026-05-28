import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.database import AsyncSessionLocal
from app.services import alert_service

logger = logging.getLogger(__name__)

CST = ZoneInfo("Asia/Shanghai")

_scan_task: asyncio.Task | None = None


async def _run_alert_scan() -> None:
    """执行预警扫描"""
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


def _seconds_until_next(hour: int, minute: int) -> float:
    """计算距离下一次 hh:mm（Asia/Shanghai）还剩多少秒"""
    now = datetime.now(CST)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


async def _alert_scan_loop() -> None:
    """每天 00:05 执行一次预警扫描的后台循环"""
    while True:
        try:
            sleep_seconds = _seconds_until_next(hour=0, minute=5)
            logger.info("下次预警扫描将在 %.1f 分钟后执行", sleep_seconds / 60)
            await asyncio.sleep(sleep_seconds)
            await _run_alert_scan()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("预警扫描循环异常，60 秒后重试")
            await asyncio.sleep(60)


def start_scheduler() -> asyncio.Task:
    """启动预警扫描后台任务，返回 Task 句柄供 shutdown 时取消"""
    global _scan_task
    _scan_task = asyncio.create_task(_alert_scan_loop())
    logger.info("预警扫描后台任务已启动")
    return _scan_task


def stop_scheduler() -> None:
    """取消预警扫描后台任务"""
    global _scan_task
    if _scan_task and not _scan_task.done():
        _scan_task.cancel()
        logger.info("预警扫描后台任务已停止")
