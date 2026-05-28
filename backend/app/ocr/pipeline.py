"""
OCR 识别流水线编排

流程：图像预处理 → qwen-vl-ocr 识别 → 正则兜底解析 → 双路合并
合并策略：模型抽取字段为主，空缺字段用正则在 raw_text 上补全。
"""
import logging
import re
import calendar
from dataclasses import dataclass

from app.ocr.image_preprocess import preprocess_image
from app.ocr.qwen_ocr_client import recognize_drug
from app.ocr.text_parser import _normalize_date_str, parse_drug_info
from app.schemas.ocr import ExtractedDrugData

logger = logging.getLogger(__name__)

_ALL_FIELDS = (
    "name", "approval_number", "manufacturer", "specification",
    "batch_number", "production_date", "expiry_date", "quantity",
)

_EMPTY_STRING_VALUES = {"null", "none", "undefined", "nan", "n/a", "na", "无", "暂无", "未识别", "未提及", "未知", "不详"}
_SHELF_LIFE_RE = re.compile(
    r"(?:有\s*效\s*期|保\s*质\s*期)[】至：:.\s]*(?:为|是)?\s*(\d{1,3})\s*(个\s*月|月|年)"
)


@dataclass
class RecognitionResult:
    """识别流水线输出"""
    raw_text: str
    extracted: ExtractedDrugData
    confidence: float          # 字段完整度 = 非空字段数 / 8，作为置信度代理


def _is_empty(value) -> bool:
    """字段是否为空（None 或纯空白字符串）"""
    if value is None:
        return True
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return True
        if stripped.lower() in _EMPTY_STRING_VALUES:
            return True
    return False


def _coerce(field: str, value):
    """把模型字段值规整为 ExtractedDrugData 所需类型；无法规整返回 None"""
    if _is_empty(value):
        return None
    if field in ("production_date", "expiry_date"):
        return _normalize_date_str(str(value))
    if field == "quantity":
        try:
            return int(value)
        except (ValueError, TypeError):
            return None
    return str(value).strip()


def _normalize_for_presence(value: str) -> str:
    return re.sub(r"[\s:：,，.。;；\-]", "", value.strip().lower())


def _is_supported_by_raw_text(field: str, value, raw_text: str) -> bool:
    """强身份字段必须能在 raw_text 中找到，防止模型把提示词示例当成识别值。"""
    if field != "approval_number":
        return True
    if not raw_text:
        return False
    return _normalize_for_presence(str(value)) in _normalize_for_presence(raw_text)


def _extract_shelf_life_months(raw_text: str) -> int | None:
    if not raw_text:
        return None
    match = _SHELF_LIFE_RE.search(raw_text)
    if not match:
        return None

    amount = int(match.group(1))
    unit = re.sub(r"\s+", "", match.group(2))
    months = amount * 12 if unit == "年" else amount
    return months if 0 < months <= 600 else None


def _add_months(date_value: str, months: int) -> str | None:
    normalized = _normalize_date_str(date_value)
    if not normalized:
        return None

    year, month, day = (int(part) for part in normalized.split("-"))
    month_index = month - 1 + months
    target_year = year + month_index // 12
    target_month = month_index % 12 + 1
    target_day = min(day, calendar.monthrange(target_year, target_month)[1])
    return f"{target_year:04d}-{target_month:02d}-{target_day:02d}"


def _derive_expiry_date_from_shelf_life(production_date: str | None, raw_text: str) -> str | None:
    if _is_empty(production_date):
        return None
    shelf_life_months = _extract_shelf_life_months(raw_text)
    if shelf_life_months is None:
        return None
    return _add_months(str(production_date), shelf_life_months)


def _merge(model_fields: dict, regex: ExtractedDrugData, raw_text: str = "") -> ExtractedDrugData:
    """双路合并：模型抽取字段为主，空缺用正则兜底结果补全。"""
    data = {}
    for field in _ALL_FIELDS:
        model_value = _coerce(field, model_fields.get(field))
        if model_value is not None and not _is_supported_by_raw_text(field, model_value, raw_text):
            model_value = None
        data[field] = model_value if model_value is not None else getattr(regex, field)
    if _is_empty(data.get("expiry_date")):
        data["expiry_date"] = _derive_expiry_date_from_shelf_life(data.get("production_date"), raw_text)
    return ExtractedDrugData(**data)


def _completeness(extracted: ExtractedDrugData) -> float:
    """字段完整度：非空字段数 / 总字段数，作为置信度代理"""
    filled = sum(1 for f in _ALL_FIELDS if not _is_empty(getattr(extracted, f)))
    return round(filled / len(_ALL_FIELDS), 2)


async def recognize_and_extract(image_bytes: bytes) -> RecognitionResult:
    """识别流水线主入口，供 ocr_service 调用。"""
    processed = preprocess_image(image_bytes)

    ocr = await recognize_drug(processed)
    raw_text = ocr.get("raw_text", "")
    model_fields = ocr.get("fields", {})

    # 正则兜底：在 qwen-vl-ocr 的高质量文本上解析
    regex_extracted = parse_drug_info(raw_text)

    merged = _merge(model_fields, regex_extracted, raw_text=raw_text)
    logger.info("[Pipeline] 识别完成，字段完整度 %.2f", _completeness(merged))

    return RecognitionResult(
        raw_text=raw_text,
        extracted=merged,
        confidence=_completeness(merged),
    )
