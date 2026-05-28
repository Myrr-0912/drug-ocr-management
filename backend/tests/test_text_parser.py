import app.ocr.text_parser as tp
from app.ocr.text_parser import parse_drug_info


def test_parse_extracts_core_fields_via_regex():
    raw = "\n".join([
        "阿莫西林胶囊",
        "批准文号：国药准字H20044416",
        "批号：20240315",
        "生产日期：2024-03-15",
        "有效期至：2026-03-01",
    ])
    result = parse_drug_info(raw)
    assert result.name == "阿莫西林胶囊"
    assert result.approval_number == "国药准字H20044416"
    assert result.batch_number == "20240315"
    assert result.production_date == "2024-03-15"
    assert result.expiry_date == "2026-03-01"


def test_parse_empty_text_returns_all_none():
    result = parse_drug_info("")
    assert result.name is None
    assert result.batch_number is None
    assert result.expiry_date is None


def test_deepseek_tier3_removed():
    # 精简后不应再保留任何 DeepSeek/LLM 兜底符号
    assert not hasattr(tp, "_extract_via_llm")
    assert not hasattr(tp, "_LLM_SYSTEM_PROMPT")
