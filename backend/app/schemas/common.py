from typing import Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """统一 API 响应格式"""
    code: int = 200
    message: str = "success"
    data: T | None = None


class PageRequest(BaseModel):
    """分页请求参数"""
    page: int = 1
    page_size: int = 20


class PageResponse(BaseModel, Generic[T]):
    """分页响应格式"""
    items: list[T]
    total: int
    page: int
    page_size: int


def ok(data: T = None, message: str = "success") -> dict:
    """快速构建成功响应"""
    return {"code": 200, "message": message, "data": data}
