from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RequireLogin
from app.core.exceptions import BusinessError
from app.database import get_db
from app.models.user import User
from app.schemas.common import PageResponse, ok
from app.schemas.ocr import OcrConfirmRequest, OcrConfirmResponse, OcrListQuery, OcrRecordResponse
from app.services import ocr_service

router = APIRouter(prefix="/ocr", tags=["OCR 识别"])


@router.post("/upload", summary="上传图片并识别")
async def upload_and_recognize(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] | None = File(None, description="同一药盒不同面的多张图片"),
    file: UploadFile | None = File(None, description="兼容旧版单图上传字段"),
    db: AsyncSession = Depends(get_db),
    current_user: User = RequireLogin,
):
    """上传同一药盒的一张或多张包装图片，创建 OCR 记录，并在后台触发识别。"""
    upload_files: list[UploadFile] = []
    if files:
        upload_files.extend(files)
    if file:
        upload_files.append(file)
    if not upload_files:
        raise BusinessError("请至少上传一张药品包装图片")

    image_payloads = [
        ocr_service.UploadImagePayload(
            image_bytes=await upload_file.read(),
            filename=upload_file.filename or f"upload-{index}.jpg",
            content_type=upload_file.content_type or "image/jpeg",
        )
        for index, upload_file in enumerate(upload_files, start=1)
    ]

    record = await ocr_service.create_upload_record_multi(
        db=db,
        images=image_payloads,
        operator_id=current_user.id,
    )
    await db.commit()
    background_tasks.add_task(
        ocr_service.recognize_record_images_background,
        record.id,
        [payload.image_bytes for payload in image_payloads],
    )
    return ok(OcrRecordResponse.model_validate(record), "识别任务已提交")


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


@router.post("/{record_id}/pause", summary="暂停 OCR 识别任务")
async def pause_record(
    record_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = RequireLogin,
):
    """暂停正在后台识别的 OCR 任务。已经发出的单次 OCR 调用会在写回前检查暂停状态。"""
    record = await ocr_service.pause_record(db=db, record_id=record_id)
    await db.commit()
    return ok(OcrRecordResponse.model_validate(record), "识别任务已暂停")


@router.post("/{record_id}/resume", summary="继续 OCR 识别任务")
async def resume_record(
    record_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _: User = RequireLogin,
):
    """继续已暂停的 OCR 任务，从已保存的图片文件重新投递后台识别。"""
    record = await ocr_service.resume_record(db=db, record_id=record_id)
    image_bytes_list = ocr_service.load_record_image_bytes(record)
    await db.commit()
    background_tasks.add_task(
        ocr_service.recognize_record_images_background,
        record.id,
        image_bytes_list,
    )
    return ok(OcrRecordResponse.model_validate(record), "识别任务已恢复")


@router.get("", summary="OCR 记录列表")
async def list_records(
    status: str | None = Query(None, description="按状态筛选 (pending/paused/success/failed/confirmed)"),
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
    current_user: User = RequireLogin,
):
    """删除识别记录；管理员可删已确认记录，普通用户不可"""
    await ocr_service.delete_record(db=db, record_id=record_id, is_admin=current_user.role == "admin")
    await db.commit()
    return ok(None, "删除成功")
