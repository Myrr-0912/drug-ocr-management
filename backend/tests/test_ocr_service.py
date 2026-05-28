import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock

from app.core.exceptions import BusinessError
from app.ocr.multi_image_consistency import LlmConsistencyJudgement
from app.models.ocr_record import OcrStatus
from app.models.ocr_record import OcrRecord
from app.models.ocr_record_image import OcrRecordImage
from app.ocr.pipeline import RecognitionResult
from app.schemas.ocr import ExtractedDrugData, OcrRecordResponse
from app.services import ocr_service
from app.services.ocr_service import UploadImagePayload


class _FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _FakeSession:
    """最小异步 DB 会话替身：仅支持 add/flush/refresh"""
    def __init__(self, record=None):
        self.added = []
        self.record = record
        self.refreshed = []

    def add(self, obj):
        self.added.append(obj)

    async def execute(self, stmt):
        return _FakeResult(self.record)

    async def flush(self):
        pass

    async def refresh(self, obj, attribute_names=None):
        self.refreshed.append((obj, tuple(attribute_names or [])))
        pass


class _PauseAfterSecondStatusRefreshSession(_FakeSession):
    def __init__(self, record):
        super().__init__(record)
        self.status_refresh_count = 0

    async def refresh(self, obj, attribute_names=None):
        if obj is self.record and attribute_names == ["status"]:
            self.status_refresh_count += 1
            if self.status_refresh_count >= 2:
                obj.status = OcrStatus.paused


async def test_upload_and_recognize_writes_pipeline_result(monkeypatch, tmp_path):
    monkeypatch.setattr(ocr_service.settings, "upload_dir", str(tmp_path))

    fake_result = RecognitionResult(
        raw_text="阿莫西林胶囊",
        extracted=ExtractedDrugData(name="阿莫西林胶囊", batch_number="20240315"),
        confidence=0.25,
    )
    monkeypatch.setattr(ocr_service, "recognize_and_extract", AsyncMock(return_value=fake_result))

    record = await ocr_service.upload_and_recognize(
        db=_FakeSession(),
        image_bytes=b"fake-image-bytes",
        filename="test.jpg",
        content_type="image/jpeg",
        operator_id=1,
    )

    assert record.status == OcrStatus.success
    assert record.raw_text == "阿莫西林胶囊"
    assert record.confidence == 0.25
    assert record.extracted_data["name"] == "阿莫西林胶囊"
    assert record.extracted_data["confidence_estimated"] is True


async def test_create_upload_record_returns_pending_without_recognizing(monkeypatch, tmp_path):
    monkeypatch.setattr(ocr_service.settings, "upload_dir", str(tmp_path))
    recognize = AsyncMock()
    monkeypatch.setattr(ocr_service, "recognize_and_extract", recognize)

    record = await ocr_service.create_upload_record(
        db=_FakeSession(),
        image_bytes=b"fake-image-bytes",
        filename="test.jpg",
        content_type="image/jpeg",
        operator_id=1,
    )

    assert record.status == OcrStatus.pending
    assert record.raw_text is None
    assert len(record.images) == 1
    assert record.images[0].status == OcrStatus.pending
    recognize.assert_not_awaited()


async def test_upload_and_recognize_rejects_bad_content_type(monkeypatch, tmp_path):
    monkeypatch.setattr(ocr_service.settings, "upload_dir", str(tmp_path))
    with pytest.raises(BusinessError):
        await ocr_service.upload_and_recognize(
            db=_FakeSession(),
            image_bytes=b"x",
            filename="test.txt",
            content_type="text/plain",
            operator_id=1,
        )


async def test_create_upload_record_multi_creates_child_images(monkeypatch, tmp_path):
    monkeypatch.setattr(ocr_service.settings, "upload_dir", str(tmp_path))
    db = _FakeSession()

    record = await ocr_service.create_upload_record_multi(
        db=db,
        images=[
            UploadImagePayload(b"first", "front.jpg", "image/jpeg"),
            UploadImagePayload(b"second", "side.png", "image/png"),
        ],
        operator_id=3,
    )

    assert record.status == OcrStatus.pending
    assert record.image_path.startswith("ocr/")
    assert len(record.images) == 2
    assert [image.image_index for image in record.images] == [1, 2]
    assert [image.status for image in record.images] == [OcrStatus.pending, OcrStatus.pending]
    for image in record.images:
        assert (image, ("created_at", "updated_at")) in db.refreshed


async def test_create_upload_record_multi_rejects_too_many_images(monkeypatch, tmp_path):
    monkeypatch.setattr(ocr_service.settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(ocr_service.settings, "max_ocr_images_per_record", 2, raising=False)

    with pytest.raises(BusinessError, match="最多"):
        await ocr_service.create_upload_record_multi(
            db=_FakeSession(),
            images=[
                UploadImagePayload(b"1", "1.jpg", "image/jpeg"),
                UploadImagePayload(b"2", "2.jpg", "image/jpeg"),
                UploadImagePayload(b"3", "3.jpg", "image/jpeg"),
            ],
            operator_id=3,
        )


async def test_recognize_record_images_merges_consistent_fields_without_llm(monkeypatch, tmp_path):
    monkeypatch.setattr(ocr_service.settings, "upload_dir", str(tmp_path))
    recognize = AsyncMock(side_effect=[
        RecognitionResult(
            raw_text="通用名称：药品甲\n国药准字H00000001",
            extracted=ExtractedDrugData(name="药品甲", approval_number="国药准字H00000001"),
            confidence=0.25,
        ),
        RecognitionResult(
            raw_text="国药准字H00000001\n批号：B001\n有效期至：2026-01-01",
            extracted=ExtractedDrugData(
                approval_number="国药准字H00000001",
                batch_number="B001",
                expiry_date="2026-01-01",
            ),
            confidence=0.38,
        ),
    ])
    judge = AsyncMock()
    monkeypatch.setattr(ocr_service, "recognize_and_extract", recognize)
    monkeypatch.setattr(ocr_service.deepseek_consistency_client, "judge_same_drug", judge)

    record = await ocr_service.create_upload_record_multi(
        db=_FakeSession(),
        images=[
            UploadImagePayload(b"front", "front.jpg", "image/jpeg"),
            UploadImagePayload(b"side", "side.jpg", "image/jpeg"),
        ],
        operator_id=1,
    )

    await ocr_service.recognize_record_images(db=_FakeSession(), record=record, image_bytes_list=[b"front", b"side"])

    assert record.status == OcrStatus.success
    assert record.extracted_data["name"] == "药品甲"
    assert record.extracted_data["batch_number"] == "B001"
    assert record.extracted_data["multi_image"]["consistency"]["status"] == "passed"
    assert record.extracted_data["multi_image"]["consistency"]["batch_confirm_allowed"] is True
    assert [image.status for image in record.images] == [OcrStatus.success, OcrStatus.success]
    judge.assert_not_awaited()


async def test_recognize_record_images_fails_on_conflicting_identity(monkeypatch, tmp_path):
    monkeypatch.setattr(ocr_service.settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(ocr_service, "recognize_and_extract", AsyncMock(side_effect=[
        RecognitionResult(
            raw_text="通用名称：药品甲\n国药准字H00000001",
            extracted=ExtractedDrugData(name="药品甲", approval_number="国药准字H00000001"),
            confidence=0.12,
        ),
        RecognitionResult(
            raw_text="通用名称：药品甲\n国药准字H00000002",
            extracted=ExtractedDrugData(name="药品甲", approval_number="国药准字H00000002"),
            confidence=0.12,
        ),
    ]))
    judge = AsyncMock()
    monkeypatch.setattr(ocr_service.deepseek_consistency_client, "judge_same_drug", judge)

    record = await ocr_service.create_upload_record_multi(
        db=_FakeSession(),
        images=[
            UploadImagePayload(b"front", "front.jpg", "image/jpeg"),
            UploadImagePayload(b"side", "side.jpg", "image/jpeg"),
        ],
        operator_id=1,
    )

    await ocr_service.recognize_record_images(db=_FakeSession(), record=record, image_bytes_list=[b"front", b"side"])

    assert record.status == OcrStatus.failed
    assert "批准文号" in record.error_message
    assert record.extracted_data["multi_image"]["consistency"]["status"] == "failed"
    assert record.extracted_data["multi_image"]["consistency"]["batch_confirm_allowed"] is False
    judge.assert_not_awaited()


async def test_recognize_record_images_calls_llm_when_no_overlap_and_keeps_manual_review(monkeypatch, tmp_path):
    monkeypatch.setattr(ocr_service.settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(ocr_service, "recognize_and_extract", AsyncMock(side_effect=[
        RecognitionResult(
            raw_text="通用名称：药品甲",
            extracted=ExtractedDrugData(name="药品甲"),
            confidence=0.12,
        ),
        RecognitionResult(
            raw_text="生产企业：厂家甲",
            extracted=ExtractedDrugData(manufacturer="厂家甲"),
            confidence=0.12,
        ),
    ]))
    judge = AsyncMock(return_value=LlmConsistencyJudgement(
        same_drug="likely",
        confidence=0.7,
        decision="pass",
        reason="未发现冲突",
        evidence=["图片1含药品名称", "图片2含生产企业"],
        risk_notes=["缺少共同字段，需人工审核"],
    ))
    monkeypatch.setattr(ocr_service.deepseek_consistency_client, "judge_same_drug", judge)

    record = await ocr_service.create_upload_record_multi(
        db=_FakeSession(),
        images=[
            UploadImagePayload(b"front", "front.jpg", "image/jpeg"),
            UploadImagePayload(b"side", "side.jpg", "image/jpeg"),
        ],
        operator_id=1,
    )

    await ocr_service.recognize_record_images(db=_FakeSession(), record=record, image_bytes_list=[b"front", b"side"])

    assert record.status == OcrStatus.success
    assert record.extracted_data["multi_image"]["consistency"]["status"] == "review_required"
    assert record.extracted_data["multi_image"]["consistency"]["review_required"] is True
    assert record.extracted_data["multi_image"]["consistency"]["batch_confirm_allowed"] is False
    assert record.extracted_data["multi_image"]["consistency"]["llm_judgement"]["same_drug"] == "likely"
    judge.assert_awaited_once()


async def test_recognize_record_images_calls_llm_for_soft_identity_conflicts(monkeypatch, tmp_path):
    monkeypatch.setattr(ocr_service.settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(ocr_service, "recognize_and_extract", AsyncMock(side_effect=[
        RecognitionResult(
            raw_text="克洛己新干混悬剂",
            extracted=ExtractedDrugData(name="克洛己新干混悬剂"),
            confidence=0.12,
        ),
        RecognitionResult(
            raw_text="金振口服液",
            extracted=ExtractedDrugData(name="金振口服液"),
            confidence=0.12,
        ),
    ]))
    judge = AsyncMock(return_value=LlmConsistencyJudgement(
        same_drug="likely",
        confidence=0.61,
        decision="review",
        reason="名称有冲突，需要人工核对",
        evidence=["两张图均来自同一上传任务"],
        risk_notes=["名称冲突"],
    ))
    monkeypatch.setattr(ocr_service.deepseek_consistency_client, "judge_same_drug", judge)

    record = await ocr_service.create_upload_record_multi(
        db=_FakeSession(),
        images=[
            UploadImagePayload(b"front", "front.jpg", "image/jpeg"),
            UploadImagePayload(b"side", "side.jpg", "image/jpeg"),
        ],
        operator_id=1,
    )

    await ocr_service.recognize_record_images(db=_FakeSession(), record=record, image_bytes_list=[b"front", b"side"])

    assert record.status == OcrStatus.success
    assert record.extracted_data["multi_image"]["consistency"]["status"] == "review_required"
    assert record.extracted_data["multi_image"]["consistency"]["method"] == "llm_soft_conflict"
    assert record.extracted_data["multi_image"]["consistency"]["batch_confirm_allowed"] is False
    judge.assert_awaited_once()


async def test_recognize_record_images_keeps_llm_error_type_when_message_empty(monkeypatch, tmp_path):
    class SilentLlmError(Exception):
        def __str__(self):
            return ""

    monkeypatch.setattr(ocr_service.settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(ocr_service, "recognize_and_extract", AsyncMock(side_effect=[
        RecognitionResult(
            raw_text="药品甲",
            extracted=ExtractedDrugData(name="药品甲"),
            confidence=0.12,
        ),
        RecognitionResult(
            raw_text="药品乙",
            extracted=ExtractedDrugData(name="药品乙"),
            confidence=0.12,
        ),
    ]))
    judge = AsyncMock(side_effect=SilentLlmError())
    monkeypatch.setattr(ocr_service.deepseek_consistency_client, "judge_same_drug", judge)

    record = await ocr_service.create_upload_record_multi(
        db=_FakeSession(),
        images=[
            UploadImagePayload(b"front", "front.jpg", "image/jpeg"),
            UploadImagePayload(b"side", "side.jpg", "image/jpeg"),
        ],
        operator_id=1,
    )

    await ocr_service.recognize_record_images(db=_FakeSession(), record=record, image_bytes_list=[b"front", b"side"])

    consistency = record.extracted_data["multi_image"]["consistency"]
    assert consistency["method"] == "llm_soft_conflict"
    assert consistency["llm_error"] == "SilentLlmError"
    assert "LLM 调用失败" in consistency["message"]
    judge.assert_awaited_once()


async def test_recognize_record_images_limits_per_record_concurrency(monkeypatch, tmp_path):
    monkeypatch.setattr(ocr_service.settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(ocr_service.settings, "qwen_ocr_per_record_concurrency", 2, raising=False)

    active = 0
    max_active = 0

    async def fake_recognize(image_bytes: bytes):
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.01)
        active -= 1
        label = image_bytes.decode("ascii")
        return RecognitionResult(
            raw_text=f"{label}\n国药准字H00000001",
            extracted=ExtractedDrugData(approval_number="国药准字H00000001"),
            confidence=0.12,
        )

    monkeypatch.setattr(ocr_service, "recognize_and_extract", fake_recognize)
    monkeypatch.setattr(ocr_service.deepseek_consistency_client, "judge_same_drug", AsyncMock())

    record = await ocr_service.create_upload_record_multi(
        db=_FakeSession(),
        images=[
            UploadImagePayload(b"front", "front.jpg", "image/jpeg"),
            UploadImagePayload(b"side", "side.jpg", "image/jpeg"),
            UploadImagePayload(b"back", "back.jpg", "image/jpeg"),
        ],
        operator_id=1,
    )

    await ocr_service.recognize_record_images(
        db=_FakeSession(),
        record=record,
        image_bytes_list=[b"front", b"side", b"back"],
    )

    assert max_active == 2
    assert record.status == OcrStatus.success
    assert [image.status for image in record.images] == [
        OcrStatus.success,
        OcrStatus.success,
        OcrStatus.success,
    ]


async def test_pause_record_marks_pending_record_and_images_paused():
    record = OcrRecord(id=20, image_path="ocr/a.jpg", status=OcrStatus.pending)
    record.images = [
        OcrRecordImage(id=1, image_path="ocr/a.jpg", image_index=1, status=OcrStatus.pending),
        OcrRecordImage(id=2, image_path="ocr/b.jpg", image_index=2, status=OcrStatus.success),
    ]

    result = await ocr_service.pause_record(db=_FakeSession(record), record_id=20)

    assert result.status == OcrStatus.paused
    assert record.images[0].status == OcrStatus.paused
    assert record.images[1].status == OcrStatus.success


async def test_pause_record_rejects_finished_record():
    record = OcrRecord(id=20, image_path="ocr/a.jpg", status=OcrStatus.success)

    with pytest.raises(BusinessError, match="识别中"):
        await ocr_service.pause_record(db=_FakeSession(record), record_id=20)


async def test_resume_record_marks_paused_record_and_images_pending():
    record = OcrRecord(id=21, image_path="ocr/a.jpg", status=OcrStatus.paused)
    record.images = [
        OcrRecordImage(id=1, image_path="ocr/a.jpg", image_index=1, status=OcrStatus.paused),
    ]

    result = await ocr_service.resume_record(db=_FakeSession(record), record_id=21)

    assert result.status == OcrStatus.pending
    assert record.images[0].status == OcrStatus.pending
    assert result.error_message is None


async def test_resume_record_rejects_non_paused_record():
    record = OcrRecord(id=21, image_path="ocr/a.jpg", status=OcrStatus.pending)

    with pytest.raises(BusinessError, match="暂停"):
        await ocr_service.resume_record(db=_FakeSession(record), record_id=21)


async def test_recognize_record_images_aborts_when_record_pauses_before_write(monkeypatch):
    record = OcrRecord(id=22, image_path="ocr/a.jpg", status=OcrStatus.pending)
    record.images = [
        OcrRecordImage(id=1, image_path="ocr/a.jpg", image_index=1, status=OcrStatus.pending),
    ]
    db = _PauseAfterSecondStatusRefreshSession(record)
    monkeypatch.setattr(ocr_service, "recognize_and_extract", AsyncMock(return_value=RecognitionResult(
        raw_text="真实 OCR 文本",
        extracted=ExtractedDrugData(name="药品甲"),
        confidence=0.12,
    )))

    await ocr_service.recognize_record_images(db=db, record=record, image_bytes_list=[b"image"])

    assert record.status == OcrStatus.paused
    assert record.raw_text is None
    assert record.images[0].raw_text is None


def test_ocr_record_response_includes_child_images():
    created_at = datetime(2026, 5, 24, 12, 0, 0)
    record = OcrRecord(
        id=7,
        image_path="ocr/cover.jpg",
        status=OcrStatus.success,
        created_at=created_at,
    )
    record.images = [
        OcrRecordImage(
            id=11,
            ocr_record_id=7,
            image_path="ocr/second.jpg",
            image_index=2,
            status=OcrStatus.success,
            raw_text="第二张",
            extracted_data={"manufacturer": "厂家甲"},
            confidence=0.25,
            created_at=created_at,
        ),
        OcrRecordImage(
            id=10,
            ocr_record_id=7,
            image_path="ocr/cover.jpg",
            image_index=1,
            status=OcrStatus.success,
            raw_text="第一张",
            extracted_data={"name": "药品甲"},
            confidence=0.25,
            created_at=created_at,
        ),
    ]

    response = OcrRecordResponse.model_validate(record)

    assert response.image_count == 2
    assert response.image_paths == ["ocr/cover.jpg", "ocr/second.jpg"]
    assert [image.image_index for image in response.images] == [1, 2]
    assert response.images[0].raw_text == "第一张"
