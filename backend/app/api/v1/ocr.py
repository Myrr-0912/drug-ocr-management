from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RequireLogin, get_current_user
from app.database import get_db
from app.models.ocr_record import OcrStatus
from app.models.user import User
from app.schemas.common import PageResponse, ok
from app.schemas.ocr import OcrConfirmRequest, OcrConfirmResponse, OcrListQuery, OcrRecordResponse
from app.services import ocr_service

router = APIRouter(prefix="/ocr", tags=["OCR 识别"])


@router.post("/upload", summary="上传图片并识别")
async def upload_and_recognize(
    file: UploadFile = File(..., description="药品图片（JPG/PNG/BMP/WebP，≤10MB）"),
    db: AsyncSession = Depends(get_db),
    current_user: User = RequireLogin,
):
    """上传药品图片，触发 OCR 识别，返回结构化提取结果供用户核对"""
    image_bytes = await file.read()
    record = await ocr_service.upload_and_recognize(
        db=db,
        image_bytes=image_bytes,
        filename=file.filename or "upload.jpg",
        content_type=file.content_type or "image/jpeg",
        operator_id=current_user.id,
    )
    await db.commit()
    return ok(OcrRecordResponse.model_validate(record), "识别完成")


@router.post("/{record_id}/confirm", summary="确认识别结果并入库")
async def confirm_record(
    record_id: int,
    data: OcrConfirmRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = RequireLogin,
):
    """用户核对并编辑识别结果后，确认入库生成药品和批次记录"""
    result = await ocr_service.confirm_record(
        db=db,
        record_id=record_id,
        data=data,
        operator_id=current_user.id,
    )
    await db.commit()
    return ok(result, "识别结果已确认入库")


@router.get("", summary="OCR 记录列表")
async def list_records(
    status: OcrStatus | None = Query(None, description="按状态筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = RequireLogin,
):
    """分页查询 OCR 识别记录，最新的在前"""
    query = OcrListQuery(status=status, page=page, page_size=page_size)
    result = await ocr_service.list_records(db=db, query=query)
    return ok(result)


@router.get("/{record_id}", summary="获取单条 OCR 记录")
async def get_record(
    record_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = RequireLogin,
):
    record = await ocr_service.get_record(db=db, record_id=record_id)
    return ok(OcrRecordResponse.model_validate(record))


@router.delete("/{record_id}", summary="删除 OCR 记录")
async def delete_record(
    record_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = RequireLogin,
):
    """删除识别记录（已确认入库的记录不允许删除）"""
    await ocr_service.delete_record(db=db, record_id=record_id)
    await db.commit()
    return ok(None, "删除成功")
