"""
OCR 识别流水线编排

流程：图像预处理 → qwen-vl-ocr 识别 → 正则兜底解析 → 双路合并
合并策略：模型抽取字段为主，空缺字段用正则在 raw_text 上补全。
"""
import logging
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
    if isinstance(value, str) and not value.strip():
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


def _merge(model_fields: dict, regex: ExtractedDrugData) -> ExtractedDrugData:
    """双路合并：模型抽取字段为主，空缺用正则兜底结果补全。"""
    data = {}
    for field in _ALL_FIELDS:
        model_value = _coerce(field, model_fields.get(field))
        data[field] = model_value if model_value is not None else getattr(regex, field)
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

    merged = _merge(model_fields, regex_extracted)
    logger.info("[Pipeline] 识别完成，字段完整度 %.2f", _completeness(merged))

    return RecognitionResult(
        raw_text=raw_text,
        extracted=merged,
        confidence=_completeness(merged),
    )
