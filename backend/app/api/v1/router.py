from fastapi import APIRouter
from app.api.v1 import auth, drugs, ocr, batches, inventory, alerts

api_router = APIRouter(prefix="/api/v1")

# 认证模块
api_router.include_router(auth.router)
# 药品管理模块
api_router.include_router(drugs.router)
# OCR 识别模块
api_router.include_router(ocr.router)
# 批次管理模块
api_router.include_router(batches.router)
# 库存管理模块
api_router.include_router(inventory.router)
# 预警管理模块
api_router.include_router(alerts.router)
