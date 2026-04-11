from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import os

from app.config import settings
from app.api.v1.router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期事件"""
    # 确保上传目录存在
    os.makedirs(settings.upload_dir, exist_ok=True)
    yield
    # 清理资源（后续添加 APScheduler 关闭）


app = FastAPI(
    title="药品信息识别与智能管理系统",
    description="基于 AI OCR 的药品信息识别与智能管理平台",
    version="1.0.0",
    lifespan=lifespan,
)

# 跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(api_router)

# 静态文件（上传的药品图片）
if os.path.exists(settings.upload_dir):
    app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局未处理异常兜底"""
    return JSONResponse(
        status_code=500,
        content={"code": 500, "message": "服务器内部错误，请联系管理员", "data": None},
    )


@app.get("/health", tags=["健康检查"])
async def health_check():
    return {"status": "ok", "service": "药品管理系统"}
