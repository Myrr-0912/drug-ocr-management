"""
OCR 业务服务层
负责：图片上传保存、调用 OCR 识别、存储记录、确认入库（创建/关联 Drug + DrugBatch）
"""
import os
import uuid
import logging
from datetime import date

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import NotFoundError, BusinessError
from app.models.ocr_record import OcrRecord, OcrStatus
from app.models.drug import Drug
from app.models.batch import DrugBatch, BatchStatus
from app.models.inventory import InventoryRecord, OperationType
from app.ocr.alibaba_client import recognize_image
from app.ocr.text_parser import parse_drug_info
from app.schemas.common import PageResponse
from app.schemas.ocr import (
    OcrRecordResponse,
    OcrConfirmRequest,
    OcrConfirmResponse,
    OcrListQuery,
)

logger = logging.getLogger(__name__)

# 允许上传的图片 MIME 类型白名单
_ALLOWED_CONTENT_TYPES = {
    "image/jpeg", "image/jpg", "image/png",
    "image/bmp", "image/webp",
}


async def upload_and_recognize(
    db: AsyncSession,
    image_bytes: bytes,
    filename: str,
    content_type: str,
    operator_id: int,
) -> OcrRecord:
    """
    上传图片并调用 OCR 识别，将结果存入 ocr_records 表。
    整个流程：保存文件 → 创建记录(pending) → OCR 识别 → 更新记录(success/failed)
    """
    # 1. 文件类型校验
    if content_type not in _ALLOWED_CONTENT_TYPES:
        raise BusinessError(f"不支持的图片格式：{content_type}，请上传 JPG/PNG/BMP/WebP")

    # 2. 大小校验
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(image_bytes) > max_bytes:
        raise BusinessError(f"图片大小超限，最大允许 {settings.max_upload_size_mb} MB")

    # 3. 保存图片到 uploads/ocr/ 目录，用 UUID 命名防冲突
    ext = os.path.splitext(filename)[-1].lower() or ".jpg"
    save_dir = os.path.join(settings.upload_dir, "ocr")
    os.makedirs(save_dir, exist_ok=True)
    save_name = f"{uuid.uuid4().hex}{ext}"
    save_path = os.path.join(save_dir, save_name)

    with open(save_path, "wb") as f:
        f.write(image_bytes)

    # 相对路径存库（前端通过 /uploads/ocr/{save_name} 访问）
    relative_path = f"ocr/{save_name}"

    # 4. 创建 pending 状态的 OCR 记录
    record = OcrRecord(
        image_path=relative_path,
        status=OcrStatus.pending,
        operator_id=operator_id,
    )
    db.add(record)
    await db.flush()
    await db.refresh(record)

    # 5. 调用 OCR（网络失败不抛出，而是将错误写入记录）
    try:
        ocr_result = await recognize_image(image_bytes)
        raw_text = ocr_result.get("raw_text", "")
        confidence = ocr_result.get("confidence", 0.0)
        confidence_estimated = ocr_result.get("confidence_estimated", False)

        # 6. 解析结构化药品信息
        extracted = parse_drug_info(raw_text)

        extracted_dict = extracted.model_dump(exclude_none=True)
        extracted_dict["confidence_estimated"] = confidence_estimated  # 记录置信度来源

        record.raw_text = raw_text
        record.extracted_data = extracted_dict
        record.confidence = confidence
        record.status = OcrStatus.success

    except Exception as e:
        logger.error("OCR 识别失败 record_id=%s: %s", record.id, e)
        record.status = OcrStatus.failed
        record.error_message = str(e)[:500]

    await db.flush()
    await db.refresh(record)
    return record


async def confirm_record(
    db: AsyncSession,
    record_id: int,
    data: OcrConfirmRequest,
    operator_id: int,
) -> OcrConfirmResponse:
    """
    确认 OCR 识别结果并入库：
    - 若提供 drug_id，则关联已有药品；否则创建新药品
    - 创建批次 DrugBatch
    - 将 OcrRecord 状态更新为 confirmed
    """
    # 1. 查找 OCR 记录
    result = await db.execute(select(OcrRecord).where(OcrRecord.id == record_id))
    record = result.scalar_one_or_none()
    if not record:
        raise NotFoundError(f"OCR 记录 {record_id} 不存在")
    if record.status == OcrStatus.confirmed:
        raise BusinessError("该记录已确认入库，请勿重复操作")
    if record.status == OcrStatus.failed:
        raise BusinessError("识别失败的记录无法确认入库")

    # 2. 获取或创建药品
    if data.drug_id:
        drug_result = await db.execute(select(Drug).where(Drug.id == data.drug_id))
        drug = drug_result.scalar_one_or_none()
        if not drug:
            raise NotFoundError(f"药品 ID {data.drug_id} 不存在")
    else:
        # 按名称+批准文号查找是否已存在（避免重复创建）
        drug_q = select(Drug).where(Drug.name == data.drug_name)
        if data.approval_number:
            drug_q = drug_q.where(Drug.approval_number == data.approval_number)
        drug_result = await db.execute(drug_q)
        drug = drug_result.scalar_one_or_none()

        if not drug:
            drug = Drug(
                name=data.drug_name,
                approval_number=data.approval_number,
                manufacturer=data.manufacturer,
                specification=data.specification,
                created_by=operator_id,
            )
            db.add(drug)
            await db.flush()
            await db.refresh(drug)

    # 3. 计算批次状态（根据有效期）
    today = date.today()
    days_to_expiry = (data.expiry_date - today).days
    if days_to_expiry < 0:
        batch_status = BatchStatus.expired
    elif days_to_expiry <= settings.expiry_warning_days:
        batch_status = BatchStatus.near_expiry
    else:
        batch_status = BatchStatus.normal

    # 4. 创建批次记录
    batch = DrugBatch(
        drug_id=drug.id,
        batch_number=data.batch_number,
        production_date=data.production_date,
        expiry_date=data.expiry_date,
        quantity=data.quantity,
        unit=data.unit,
        status=batch_status,
        source_ocr_id=record.id,
    )
    db.add(batch)
    await db.flush()
    await db.refresh(batch)

    # 5. OCR 入库时，若数量 > 0 则同步写入库存流水（IN 类型）
    if data.quantity > 0:
        inv_record = InventoryRecord(
            drug_id=drug.id,
            batch_id=batch.id,
            operation_type=OperationType.IN,
            quantity=data.quantity,
            operator_id=operator_id,
            remark=f"OCR 识别入库（记录 #{record.id}）",
        )
        db.add(inv_record)

    # 6. 更新 OCR 记录为已确认
    record.status = OcrStatus.confirmed
    record.drug_id = drug.id
    record.batch_id = batch.id

    await db.flush()

    return OcrConfirmResponse(
        ocr_id=record.id,
        drug_id=drug.id,
        batch_id=batch.id,
    )


async def get_record(db: AsyncSession, record_id: int) -> OcrRecord:
    """根据 ID 查询单条 OCR 记录"""
    result = await db.execute(select(OcrRecord).where(OcrRecord.id == record_id))
    record = result.scalar_one_or_none()
    if not record:
        raise NotFoundError(f"OCR 记录 {record_id} 不存在")
    return record


async def list_records(
    db: AsyncSession, query: OcrListQuery
) -> PageResponse[OcrRecordResponse]:
    """分页查询 OCR 记录列表"""
    stmt = select(OcrRecord)

    if query.status:
        stmt = stmt.where(OcrRecord.status == query.status)

    # 统计总数
    count_result = await db.execute(
        select(func.count()).select_from(stmt.subquery())
    )
    total = count_result.scalar_one()

    # 分页，最新记录在前
    stmt = stmt.order_by(OcrRecord.id.desc()).offset(
        (query.page - 1) * query.page_size
    ).limit(query.page_size)

    result = await db.execute(stmt)
    items = [OcrRecordResponse.model_validate(r) for r in result.scalars().all()]

    return PageResponse(
        items=items,
        total=total,
        page=query.page,
        page_size=query.page_size,
    )


async def delete_record(db: AsyncSession, record_id: int, is_admin: bool = False) -> None:
    """删除 OCR 记录；管理员可删任意状态，普通用户不可删已确认记录"""
    result = await db.execute(select(OcrRecord).where(OcrRecord.id == record_id))
    record = result.scalar_one_or_none()
    if not record:
        raise NotFoundError(f"OCR 记录 {record_id} 不存在")
    if record.status == OcrStatus.confirmed and not is_admin:
        raise BusinessError("已确认入库的记录不允许删除，如需删除请联系管理员")
    await db.delete(record)
    await db.flush()
