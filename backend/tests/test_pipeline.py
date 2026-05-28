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


def test_merge_treats_null_strings_as_empty_and_derives_expiry_from_shelf_life():
    regex = ExtractedDrugData(batch_number="2023-05-10")
    raw_text = "【有效期】24个月。【生产批号】2023-05-10"

    merged = _merge(
        {
            "batch_number": "null",
            "production_date": "2023-05-10",
            "expiry_date": "null",
        },
        regex,
        raw_text=raw_text,
    )

    assert merged.batch_number == "2023-05-10"
    assert merged.production_date == "2023-05-10"
    assert merged.expiry_date == "2025-05-10"


def test_merge_discards_model_approval_number_absent_from_raw_text():
    merged = _merge(
        {"approval_number": "国药准字H20044416"},
        ExtractedDrugData(),
        raw_text="图片只识别到了药品名称和用法用量，没有批准文号",
    )

    assert merged.approval_number is None


def test_merge_keeps_model_approval_number_present_in_raw_text():
    merged = _merge(
        {"approval_number": "国药准字H20051142"},
        ExtractedDrugData(),
        raw_text="批准文号：国药准字H20051142",
    )

    assert merged.approval_number == "国药准字H20051142"


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


async def test_recognize_and_extract_drops_hallucinated_model_approval_number(monkeypatch):
    monkeypatch.setattr(pipeline, "preprocess_image", lambda b: b)

    async def fake_ocr(_):
        return {
            "raw_text": "通用名称：克洛己新干混悬剂\n江苏正大清江制药有限公司",
            "fields": {"approval_number": "国药准字H20044416"},
        }

    monkeypatch.setattr(pipeline, "recognize_drug", fake_ocr)

    result = await pipeline.recognize_and_extract(b"image")

    assert result.extracted.approval_number is None
