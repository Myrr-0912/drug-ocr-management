from fastapi import APIRouter
from app.api.v1 import auth, drugs

api_router = APIRouter(prefix="/api/v1")

# 认证模块
api_router.include_router(auth.router)
# 药品管理模块
api_router.include_router(drugs.router)
