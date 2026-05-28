from app.ocr import pipeline
from app.ocr.pipeline import RecognitionResult, _completeness, _merge
from app.schemas.ocr import ExtractedDrugData


def test_merge_prefers_model_fields():
    model = {"name": "阿莫西林胶囊", "batch_number": "20240315"}
    regex = ExtractedDrugData(name="正则名称", batch_number="REGEXBATCH", expiry_date="2026-03-01")
    merged = _merge(model, regex)
    assert merged.name == "阿莫西林胶囊"          # 模型优先
    assert merged.batch_number == "20240315"
    assert merged.expiry_date == "2026-03-01"      # 模型空缺 → 用正则


def test_merge_fills_empty_model_fields_with_regex():
    model = {"name": None, "batch_number": ""}
    regex = ExtractedDrugData(name="正则名称", batch_number="REGEXBATCH")
    merged = _merge(model, regex)
    assert merged.name == "正则名称"
    assert merged.batch_number == "REGEXBATCH"


def test_merge_normalizes_model_dates():
    merged = _merge({"expiry_date": "2026年03月"}, ExtractedDrugData())
    assert merged.expiry_date == "2026-03-01"


def test_merge_skips_invalid_model_quantity():
    merged = _merge({"quantity": "abc"}, ExtractedDrugData(quantity=5))
    assert merged.quantity == 5


def test_completeness_ratio():
    extracted = ExtractedDrugData(
        name="药", batch_number="B", production_date="2024-03-15", expiry_date="2026-03-01",
    )
    assert _completeness(extracted) == 0.5     # 8 字段填 4 个


def test_completeness_empty():
    assert _completeness(ExtractedDrugData()) == 0.0


async def test_recognize_and_extract_merges_model_and_regex(monkeypatch):
    monkeypatch.setattr(pipeline, "preprocess_image", lambda b: b)

    async def fake_ocr(_):
        return {
            "raw_text": "阿莫西林胶囊\n批号：20240315\n有效期至：2026-03-01",
            "fields": {"name": "阿莫西林胶囊"},   # 模型只给出名称
        }

    monkeypatch.setattr(pipeline, "recognize_drug", fake_ocr)

    result = await pipeline.recognize_and_extract(b"image")
    assert result.extracted.name == "阿莫西林胶囊"        # 来自模型
    assert result.extracted.batch_number == "20240315"     # 模型空缺 → 正则补
    assert result.extracted.expiry_date == "2026-03-01"
    assert result.raw_text.startswith("阿莫西林胶囊")


async def test_recognize_and_extract_relies_on_regex_when_no_model_fields(monkeypatch):
    monkeypatch.setattr(pipeline, "preprocess_image", lambda b: b)

    async def fake_ocr(_):
        # 模型未给结构化字段（JSON 解析失败的情形），只有 raw_text
        return {
            "raw_text": "阿莫西林胶囊\n批号：20240315\n生产日期：2024-03-15\n有效期至：2026-03-01",
            "fields": {},
        }

    monkeypatch.setattr(pipeline, "recognize_drug", fake_ocr)

    result = await pipeline.recognize_and_extract(b"image")
    assert result.extracted.name == "阿莫西林胶囊"
    assert result.extracted.batch_number == "20240315"
    assert result.extracted.production_date == "2024-03-15"
    assert result.confidence > 0
