"""
OCR 业务服务层
负责：图片上传保存、调用 OCR 识别、存储记录、确认入库（创建/关联 Drug + DrugBatch）
"""
import os
import uuid
import logging
import asyncio
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Sequence

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.exceptions import NotFoundError, BusinessError, ConflictError
from app.database import AsyncSessionLocal
from app.models.ocr_record import OcrRecord, OcrStatus
from app.models.ocr_record_image import OcrRecordImage
from app.models.drug import Drug
from app.models.batch import DrugBatch, BatchStatus
from app.models.inventory import InventoryRecord, OperationType
from app.ocr import deepseek_consistency_client
from app.ocr.multi_image_consistency import ImageOcrEvidence, evaluate_multi_image_consistency
from app.ocr.pipeline import RecognitionResult, recognize_and_extract
from app.schemas.common import PageResponse
from app.schemas.ocr import (
    OcrRecordResponse,
    OcrConfirmRequest,
    OcrConfirmResponse,
    OcrListQuery,
)

logger = logging.getLogger(__name__)
_PER_RECORD_CONCURRENCY_HARD_LIMIT = 2

# 允许上传的图片 MIME 类型白名单
_ALLOWED_CONTENT_TYPES = {
    "image/jpeg", "image/jpg", "image/png",
    "image/bmp", "image/webp",
}
_EXTRACTED_FIELDS = (
    "name",
    "approval_number",
    "manufacturer",
    "specification",
    "batch_number",
    "production_date",
    "expiry_date",
    "quantity",
)


@dataclass(frozen=True)
class UploadImagePayload:
    """一次上传中的单张图片内容。"""

    image_bytes: bytes
    filename: str
    content_type: str


@dataclass(frozen=True)
class _ImageRecognitionOutcome:
    image_index: int
    child_image: OcrRecordImage | None
    result: RecognitionResult | None = None
    error_message: str | None = None


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
    record = await create_upload_record(
        db=db,
        image_bytes=image_bytes,
        filename=filename,
        content_type=content_type,
        operator_id=operator_id,
    )
    await recognize_record(db=db, record=record, image_bytes=image_bytes)
    return record


async def create_upload_record(
    db: AsyncSession,
    image_bytes: bytes,
    filename: str,
    content_type: str,
    operator_id: int,
) -> OcrRecord:
    """保存上传图片并创建 pending 记录，不等待模型识别完成。"""
    return await create_upload_record_multi(
        db=db,
        images=[UploadImagePayload(image_bytes, filename, content_type)],
        operator_id=operator_id,
    )


async def create_upload_record_multi(
    db: AsyncSession,
    images: Sequence[UploadImagePayload],
    operator_id: int,
) -> OcrRecord:
    """保存同一药盒不同面的多张图片，并创建一条 pending 主记录。"""
    if not images:
        raise BusinessError("请至少上传一张药品包装图片")
    if len(images) > settings.max_ocr_images_per_record:
        raise BusinessError(f"单次最多上传 {settings.max_ocr_images_per_record} 张同一药盒图片")

    for image in images:
        _validate_upload_image(image)

    image_paths = [_save_upload_image(image) for image in images]
    record = OcrRecord(
        image_path=image_paths[0],
        status=OcrStatus.pending,
        operator_id=operator_id,
    )
    child_images = [
        OcrRecordImage(
            image_path=image_path,
            image_index=index,
            status=OcrStatus.pending,
        )
        for index, image_path in enumerate(image_paths, start=1)
    ]
    record.images = child_images

    db.add(record)
    await db.flush()
    await db.refresh(record, attribute_names=["created_at", "updated_at"])
    for child_image in child_images:
        await db.refresh(child_image, attribute_names=["created_at", "updated_at"])
    return record


def _validate_upload_image(image: UploadImagePayload) -> None:
    if image.content_type not in _ALLOWED_CONTENT_TYPES:
        raise BusinessError(f"不支持的图片格式：{image.content_type}，请上传 JPG/PNG/BMP/WebP")

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(image.image_bytes) > max_bytes:
        raise BusinessError(f"图片大小超限，最大允许 {settings.max_upload_size_mb} MB")


def _save_upload_image(image: UploadImagePayload) -> str:
    ext = os.path.splitext(image.filename)[-1].lower() or ".jpg"
    save_dir = os.path.join(settings.upload_dir, "ocr")
    os.makedirs(save_dir, exist_ok=True)
    save_name = f"{uuid.uuid4().hex}{ext}"
    save_path = os.path.join(save_dir, save_name)

    with open(save_path, "wb") as f:
        f.write(image.image_bytes)

    return f"ocr/{save_name}"


async def recognize_record(
    db: AsyncSession,
    record: OcrRecord,
    image_bytes: bytes,
) -> OcrRecord:
    """调用识别流水线并把结果写回 OCR 记录；失败只落库，不向外抛出。"""
    return await recognize_record_images(db=db, record=record, image_bytes_list=[image_bytes])


def _per_record_ocr_concurrency() -> int:
    try:
        configured = int(settings.qwen_ocr_per_record_concurrency)
    except (TypeError, ValueError):
        configured = 2
    return min(max(1, configured), _PER_RECORD_CONCURRENCY_HARD_LIMIT)


async def _recognize_one_image(
    record_id: int | None,
    image_index: int,
    image_bytes: bytes,
    child_image: OcrRecordImage | None,
    semaphore: asyncio.Semaphore,
) -> _ImageRecognitionOutcome:
    async with semaphore:
        try:
            result = await recognize_and_extract(image_bytes)
            return _ImageRecognitionOutcome(
                image_index=image_index,
                child_image=child_image,
                result=result,
            )
        except Exception as e:
            logger.error("OCR 单图识别失败 record_id=%s image_index=%s: %s", record_id, image_index, e)
            return _ImageRecognitionOutcome(
                image_index=image_index,
                child_image=child_image,
                error_message=str(e)[:500],
            )


async def _cancel_pending_tasks(tasks: set[asyncio.Task[_ImageRecognitionOutcome]]) -> None:
    if not tasks:
        return
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


async def recognize_record_images(
    db: AsyncSession,
    record: OcrRecord,
    image_bytes_list: Sequence[bytes],
) -> OcrRecord:
    """逐张识别同一药盒不同面，并把合并结果写回主 OCR 记录。"""
    child_images = sorted(getattr(record, "images", []) or [], key=lambda image: image.image_index)
    if child_images and len(child_images) != len(image_bytes_list):
        record.status = OcrStatus.failed
        record.error_message = "上传图片数量与待识别图片记录不一致，请重新上传"
        await db.flush()
        await db.refresh(record)
        return record

    evidence: list[ImageOcrEvidence] = []
    confidences: list[float] = []
    errors: list[str] = []

    semaphore = asyncio.Semaphore(_per_record_ocr_concurrency())
    pending_tasks = {
        asyncio.create_task(_recognize_one_image(
            record_id=record.id,
            image_index=index,
            image_bytes=image_bytes,
            child_image=child_images[index - 1] if index <= len(child_images) else None,
            semaphore=semaphore,
        ))
        for index, image_bytes in enumerate(image_bytes_list, start=1)
    }

    while pending_tasks:
        if await _record_is_paused(db, record):
            await _cancel_pending_tasks(pending_tasks)
            return record

        done_tasks, pending_tasks = await asyncio.wait(
            pending_tasks,
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in done_tasks:
            outcome = task.result()
            if await _record_is_paused(db, record):
                await _cancel_pending_tasks(pending_tasks)
                return record

            child_image = outcome.child_image
            if outcome.error_message:
                errors.append(f"图片{outcome.image_index}：{outcome.error_message}")
                if child_image:
                    child_image.status = OcrStatus.failed
                    child_image.error_message = outcome.error_message
                continue

            result = outcome.result
            if result is None:
                continue

            extracted_dict = result.extracted.model_dump(exclude_none=True)
            extracted_dict["confidence_estimated"] = True

            if child_image:
                child_image.raw_text = result.raw_text
                child_image.extracted_data = extracted_dict
                child_image.confidence = result.confidence
                child_image.status = OcrStatus.success
                child_image.error_message = None

            evidence.append(ImageOcrEvidence(
                image_index=outcome.image_index,
                raw_text=result.raw_text,
                fields=extracted_dict,
            ))
            confidences.append(result.confidence)

    evidence.sort(key=lambda item: item.image_index)

    if errors:
        record.status = OcrStatus.failed
        record.error_message = "部分图片识别失败：" + "；".join(errors)
        record.raw_text = _join_evidence_raw_text(evidence)
        record.extracted_data = _single_or_partial_extracted_data(evidence)
        record.confidence = max(confidences) if confidences else None
        await db.flush()
        await db.refresh(record)
        return record

    if await _record_is_paused(db, record):
        return record

    if not evidence:
        record.status = OcrStatus.failed
        record.error_message = "未获得有效 OCR 识别结果"
        await db.flush()
        await db.refresh(record)
        return record

    if len(evidence) == 1:
        record.raw_text = evidence[0].raw_text
        record.extracted_data = dict(evidence[0].fields)
        record.confidence = confidences[0] if confidences else None
        record.status = OcrStatus.success
        record.error_message = None
        await db.flush()
        await db.refresh(record)
        return record

    consistency = evaluate_multi_image_consistency(evidence)
    if consistency.status == "review_required" and consistency.method in {"rule_no_overlap", "rule_soft_conflict"}:
        try:
            llm_judgement = await deepseek_consistency_client.judge_same_drug(evidence)
            consistency = evaluate_multi_image_consistency(evidence, llm_judgement=llm_judgement)
        except Exception as e:
            llm_error = _format_exception_for_user(e)
            logger.warning("DeepSeek 多图一致性辅助校验失败 record_id=%s: %s", record.id, llm_error)
            consistency = evaluate_multi_image_consistency(evidence, llm_error=llm_error[:500])

    record.raw_text = consistency.raw_text
    record.extracted_data = _build_multi_image_extracted_data(consistency, len(evidence))
    record.confidence = _merged_completeness(consistency.merged_fields)
    record.status = OcrStatus.failed if consistency.status == "failed" else OcrStatus.success
    record.error_message = consistency.message[:500] if consistency.status == "failed" else None

    await db.flush()
    await db.refresh(record)
    return record


async def _record_is_paused(db: AsyncSession, record: OcrRecord) -> bool:
    try:
        await db.refresh(record, attribute_names=["status"])
    except TypeError:
        await db.refresh(record)
    return record.status == OcrStatus.paused


def _join_evidence_raw_text(evidence: list[ImageOcrEvidence]) -> str | None:
    if not evidence:
        return None
    return "\n\n".join(f"[图片{item.image_index}]\n{item.raw_text}" for item in evidence)


def _single_or_partial_extracted_data(evidence: list[ImageOcrEvidence]) -> dict | None:
    if not evidence:
        return None
    if len(evidence) == 1:
        return dict(evidence[0].fields)
    merged = evaluate_multi_image_consistency(evidence)
    return _build_multi_image_extracted_data(merged, len(evidence))


def _build_multi_image_extracted_data(consistency, image_count: int) -> dict:
    data = dict(consistency.merged_fields)
    data["confidence_estimated"] = True
    data["multi_image"] = {
        "image_count": image_count,
        "merged_from_image_indexes": consistency.merged_from_image_indexes,
        "consistency": {
            "status": consistency.status,
            "method": consistency.method,
            "review_required": consistency.review_required,
            "batch_confirm_allowed": consistency.batch_confirm_allowed,
            "message": consistency.message,
            "conflicts": consistency.conflicts,
            "llm_judgement": consistency.llm_judgement,
            "llm_error": consistency.llm_error,
        },
    }
    return data


def _merged_completeness(fields: dict) -> float:
    filled = sum(1 for field in _EXTRACTED_FIELDS if not _is_empty(fields.get(field)))
    return round(filled / len(_EXTRACTED_FIELDS), 2)


def _is_empty(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def _sync_confirmed_extracted_data(record: OcrRecord, data: OcrConfirmRequest) -> None:
    extracted_data = dict(record.extracted_data or {})
    extracted_data.update(
        {
            "name": data.drug_name,
            "approval_number": data.approval_number,
            "manufacturer": data.manufacturer,
            "specification": data.specification,
            "batch_number": data.batch_number,
            "production_date": data.production_date.isoformat() if data.production_date else None,
            "expiry_date": data.expiry_date.isoformat(),
            "quantity": data.quantity,
            "unit": data.unit,
        }
    )
    record.extracted_data = extracted_data


def _normalize_identity_text(value: str | None) -> str:
    return (value or "").strip()


def _approval_number_conflict_message(
    approval_number: str,
    existing_name: str,
    requested_name: str,
) -> str:
    return (
        f"批准文号 '{approval_number}' 已属于药品 '{existing_name}'，"
        f"不能作为新药品 '{requested_name}' 入库。请恢复药品名称，"
        "或清空/更正批准文号后再确认。"
    )


def _batch_name_conflict_message(
    batch_number: str,
    existing_name: str,
    requested_name: str,
) -> str:
    return (
        f"批号 '{batch_number}' 已存在，对应药品为 '{existing_name}'，"
        f"当前确认的药品名称为 '{requested_name}'。"
        "同一照片/同一批号不能改成不同药品入库，请核对药品名称或批号后再确认。"
    )


def _format_exception_for_user(error: Exception) -> str:
    message = str(error).strip()
    error_type = type(error).__name__
    return f"{error_type}: {message}" if message else error_type


async def recognize_record_background(record_id: int, image_bytes: bytes) -> None:
    """后台识别任务入口：使用独立 DB session 更新已创建的 pending 记录。"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(OcrRecord)
            .options(selectinload(OcrRecord.images))
            .where(OcrRecord.id == record_id)
        )
        record = result.scalar_one_or_none()
        if not record:
            logger.warning("OCR 后台识别找不到记录 record_id=%s", record_id)
            return
        await recognize_record(db=db, record=record, image_bytes=image_bytes)
        await db.commit()


async def recognize_record_images_background(record_id: int, image_bytes_list: Sequence[bytes]) -> None:
    """多图后台识别任务入口：使用独立 DB session 更新 pending 主记录和图片证据。"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(OcrRecord)
            .options(selectinload(OcrRecord.images))
            .where(OcrRecord.id == record_id)
        )
        record = result.scalar_one_or_none()
        if not record:
            logger.warning("OCR 多图后台识别找不到记录 record_id=%s", record_id)
            return
        await recognize_record_images(db=db, record=record, image_bytes_list=image_bytes_list)
        await db.commit()


async def pause_record(db: AsyncSession, record_id: int) -> OcrRecord:
    """暂停正在识别的 OCR 任务。已经完成的单图结果保持不变。"""
    record = await _get_record_with_images(db, record_id)
    if record.status == OcrStatus.paused:
        return record
    if record.status != OcrStatus.pending:
        raise BusinessError("仅识别中的任务可以暂停")

    record.status = OcrStatus.paused
    record.error_message = "识别任务已暂停"
    for image in getattr(record, "images", []) or []:
        if image.status == OcrStatus.pending:
            image.status = OcrStatus.paused
            image.error_message = "识别任务已暂停"

    await db.flush()
    await db.refresh(record, attribute_names=["status", "error_message"])
    return record


async def resume_record(db: AsyncSession, record_id: int) -> OcrRecord:
    """恢复已暂停的 OCR 任务。恢复后由 API 重新投递后台识别。"""
    record = await _get_record_with_images(db, record_id)
    if record.status != OcrStatus.paused:
        raise BusinessError("仅暂停中的任务可以继续识别")

    record.status = OcrStatus.pending
    record.raw_text = None
    record.extracted_data = None
    record.confidence = None
    record.error_message = None
    for image in getattr(record, "images", []) or []:
        image.status = OcrStatus.pending
        image.raw_text = None
        image.extracted_data = None
        image.confidence = None
        image.error_message = None

    await db.flush()
    await db.refresh(record, attribute_names=["status", "error_message"])
    return record


def load_record_image_bytes(record: OcrRecord) -> list[bytes]:
    """从已保存的图片路径重新读取后台识别所需的图片内容。"""
    images = sorted(getattr(record, "images", []) or [], key=lambda image: image.image_index)
    paths = [image.image_path for image in images] or [record.image_path]
    image_bytes_list: list[bytes] = []
    for relative_path in paths:
        path = Path(settings.upload_dir) / relative_path
        if not path.exists():
            raise BusinessError(f"识别图片文件不存在：{relative_path}")
        image_bytes_list.append(path.read_bytes())
    return image_bytes_list


async def _get_record_with_images(db: AsyncSession, record_id: int) -> OcrRecord:
    result = await db.execute(
        select(OcrRecord)
        .options(selectinload(OcrRecord.images))
        .where(OcrRecord.id == record_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise NotFoundError(f"OCR 记录 {record_id} 不存在")
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
    if record.status == OcrStatus.paused:
        raise BusinessError("暂停中的识别任务无法确认入库，请先继续识别")

    # 2. 获取或创建药品
    if data.drug_id:
        drug_result = await db.execute(select(Drug).where(Drug.id == data.drug_id))
        drug = drug_result.scalar_one_or_none()
        if not drug:
            raise NotFoundError(f"药品 ID {data.drug_id} 不存在")
    else:
        drug = None
        if data.approval_number:
            existing_by_approval = await db.execute(
                select(Drug).where(Drug.approval_number == data.approval_number)
            )
            drug = existing_by_approval.scalar_one_or_none()
            if drug and _normalize_identity_text(drug.name) != _normalize_identity_text(data.drug_name):
                raise ConflictError(
                    _approval_number_conflict_message(
                        data.approval_number,
                        drug.name,
                        data.drug_name,
                    )
                )

        # 按名称+批准文号查找是否已存在（避免重复创建）
        if not drug:
            drug_q = select(Drug).where(Drug.name == data.drug_name)
            if data.approval_number:
                drug_q = drug_q.where(Drug.approval_number == data.approval_number)
            drug_result = await db.execute(drug_q)
            drug = drug_result.scalar_one_or_none()

        existing_batch_result = await db.execute(
            select(DrugBatch, Drug.name)
            .join(Drug, Drug.id == DrugBatch.drug_id)
            .where(DrugBatch.batch_number == data.batch_number)
            .order_by(DrugBatch.id.desc())
        )
        existing_batch_row = existing_batch_result.first()
        if existing_batch_row:
            existing_batch, existing_drug_name = existing_batch_row
            if _normalize_identity_text(existing_drug_name) != _normalize_identity_text(data.drug_name):
                raise ConflictError(
                    _batch_name_conflict_message(
                        data.batch_number,
                        existing_drug_name,
                        data.drug_name,
                    )
                )
            if drug and existing_batch.drug_id == drug.id:
                raise ConflictError(
                    f"药品 '{existing_drug_name}' 的批号 '{data.batch_number}' 已入库，请勿重复确认同一批次。"
                )

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
    _sync_confirmed_extracted_data(record, data)

    await db.flush()

    return OcrConfirmResponse(
        ocr_id=record.id,
        drug_id=drug.id,
        batch_id=batch.id,
    )


async def get_record(db: AsyncSession, record_id: int) -> OcrRecord:
    """根据 ID 查询单条 OCR 记录"""
    result = await db.execute(
        select(OcrRecord)
        .options(selectinload(OcrRecord.images))
        .where(OcrRecord.id == record_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise NotFoundError(f"OCR 记录 {record_id} 不存在")
    return record


async def list_records(
    db: AsyncSession, query: OcrListQuery
) -> PageResponse[OcrRecordResponse]:
    """分页查询 OCR 记录列表"""
    stmt = select(OcrRecord).options(selectinload(OcrRecord.images))

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
