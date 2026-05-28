import pytest
from unittest.mock import AsyncMock

from app.core.exceptions import BusinessError
from app.models.ocr_record import OcrStatus
from app.ocr.pipeline import RecognitionResult
from app.schemas.ocr import ExtractedDrugData
from app.services import ocr_service


class _FakeSession:
    """最小异步 DB 会话替身：仅支持 add/flush/refresh"""
    def __init__(self):
        self.added = []

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        pass

    async def refresh(self, obj):
        pass


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
