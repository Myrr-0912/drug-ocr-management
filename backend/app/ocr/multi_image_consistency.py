"""多图 OCR 字段合并与一致性校验。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal
import re
import unicodedata

from app.ocr.text_parser import _normalize_date_str


_MERGE_FIELDS = (
    "name",
    "approval_number",
    "manufacturer",
    "specification",
    "batch_number",
    "production_date",
    "expiry_date",
    "quantity",
)
_IDENTITY_FIELDS = {"approval_number", "name", "manufacturer", "specification"}
_BATCH_FIELDS = {"batch_number", "production_date", "expiry_date"}
_AUXILIARY_FIELDS = {"quantity"}
_HARD_CONFLICT_FIELDS = {"approval_number"} | _BATCH_FIELDS
_SOFT_CONFLICT_FIELDS = {"name", "manufacturer", "specification"}
_FIELD_LABELS = {
    "approval_number": "批准文号",
    "name": "药品名称",
    "manufacturer": "生产企业",
    "specification": "规格",
    "batch_number": "批号",
    "production_date": "生产日期",
    "expiry_date": "有效期",
    "quantity": "数量",
}


@dataclass
class ImageOcrEvidence:
    image_index: int
    raw_text: str
    fields: dict[str, Any]


@dataclass
class LlmConsistencyJudgement:
    same_drug: Literal["likely", "unlikely", "uncertain"]
    confidence: float
    decision: Literal["pass", "review", "fail"]
    reason: str
    evidence: list[str]
    risk_notes: list[str]


@dataclass
class MultiImageConsistencyResult:
    status: Literal["passed", "review_required", "failed"]
    method: str
    review_required: bool
    batch_confirm_allowed: bool
    message: str
    conflicts: list[dict[str, Any]]
    merged_fields: dict[str, Any]
    merged_from_image_indexes: dict[str, int]
    raw_text: str
    llm_judgement: dict[str, Any] | None = None
    llm_error: str | None = None


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def _normalize_value(field: str, value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value)).strip().lower()
    text = re.sub(r"\s+", "", text)
    if field in {"production_date", "expiry_date"}:
        return _normalize_date_str(text) or text
    if field == "approval_number":
        return re.sub(r"[\s:：,，.。;；-]", "", text)
    if field == "name":
        return re.sub(r"[\s:：,，.。;；()（）【】\[\]<>《》]", "", text)
    return text


def _collect_values(evidence: list[ImageOcrEvidence]) -> dict[str, list[tuple[int, Any, str]]]:
    values: dict[str, list[tuple[int, Any, str]]] = {field: [] for field in _MERGE_FIELDS}
    for image in evidence:
        for field in _MERGE_FIELDS:
            value = image.fields.get(field)
            if _is_empty(value):
                continue
            values[field].append((image.image_index, value, _normalize_value(field, value)))
    return values


def _build_raw_text(evidence: list[ImageOcrEvidence]) -> str:
    parts = []
    for image in sorted(evidence, key=lambda item: item.image_index):
        parts.append(f"[图片{image.image_index}]\n{image.raw_text or ''}".rstrip())
    return "\n\n".join(parts)


def _merge_fields(values: dict[str, list[tuple[int, Any, str]]]) -> tuple[dict[str, Any], dict[str, int]]:
    merged: dict[str, Any] = {}
    sources: dict[str, int] = {}
    for field, candidates in values.items():
        if not candidates:
            continue
        image_index, value, _ = candidates[0]
        merged[field] = value
        sources[field] = image_index
    return merged, sources


def _find_conflicts(values: dict[str, list[tuple[int, Any, str]]]) -> list[dict[str, Any]]:
    conflicts = []
    for field, candidates in values.items():
        normalized_groups: dict[str, list[tuple[int, Any]]] = {}
        for image_index, value, normalized in candidates:
            normalized_groups.setdefault(normalized, []).append((image_index, value))
        if len(normalized_groups) <= 1:
            continue
        conflicts.append({
            "field": field,
            "label": _FIELD_LABELS.get(field, field),
            "values": [
                {"image_index": image_index, "value": value}
                for group in normalized_groups.values()
                for image_index, value in group
            ],
        })
    return conflicts


def _has_consistent_anchor(values: dict[str, list[tuple[int, Any, str]]]) -> bool:
    for field in ("approval_number", "name"):
        candidates = values.get(field, [])
        if len({image_index for image_index, _, _ in candidates}) >= 2:
            return True

    manufacturer_values = values.get("manufacturer", [])
    specification_values = values.get("specification", [])
    combo_by_image: dict[int, tuple[str, str]] = {}
    for image_index, _, normalized in manufacturer_values:
        combo_by_image.setdefault(image_index, ["", ""])[0] = normalized  # type: ignore[index]
    for image_index, _, normalized in specification_values:
        combo_by_image.setdefault(image_index, ["", ""])[1] = normalized  # type: ignore[index]
    combos = [tuple(combo) for combo in combo_by_image.values() if combo[0] and combo[1]]
    return len(combos) >= 2 and len(set(combos)) == 1


def _failure_message(conflict: dict[str, Any]) -> str:
    label = conflict.get("label") or conflict["field"]
    if conflict["field"] in _BATCH_FIELDS:
        return f"{label}不一致，疑似不同批次或不同药盒，请只上传同一药盒的不同面。"
    return f"{label}不一致，疑似不同药盒，请只上传同一药盒的不同面。"


def evaluate_multi_image_consistency(
    evidence: list[ImageOcrEvidence],
    llm_judgement: LlmConsistencyJudgement | None = None,
    llm_error: str | None = None,
) -> MultiImageConsistencyResult:
    """对多张单图 OCR 结果做规则校验与字段合并。"""
    values = _collect_values(evidence)
    merged_fields, sources = _merge_fields(values)
    raw_text = _build_raw_text(evidence)
    conflicts = _find_conflicts(values)

    blocking_conflicts = [
        conflict for conflict in conflicts
        if conflict["field"] in _HARD_CONFLICT_FIELDS
    ]
    if blocking_conflicts:
        first = blocking_conflicts[0]
        return MultiImageConsistencyResult(
            status="failed",
            method="rule_conflict",
            review_required=False,
            batch_confirm_allowed=False,
            message=_failure_message(first),
            conflicts=blocking_conflicts,
            merged_fields=merged_fields,
            merged_from_image_indexes=sources,
            raw_text=raw_text,
        )

    soft_conflicts = [
        conflict for conflict in conflicts
        if conflict["field"] in _SOFT_CONFLICT_FIELDS
    ]
    if soft_conflicts:
        if llm_judgement and (llm_judgement.decision == "fail" or llm_judgement.same_drug == "unlikely"):
            return MultiImageConsistencyResult(
                status="failed",
                method="llm_soft_conflict",
                review_required=False,
                batch_confirm_allowed=False,
                message=llm_judgement.reason or "AI 辅助判断疑似不是同一药品。",
                conflicts=soft_conflicts,
                merged_fields=merged_fields,
                merged_from_image_indexes=sources,
                raw_text=raw_text,
                llm_judgement=asdict(llm_judgement),
            )

        message = "多张图片存在药品名称、生产企业或规格识别不一致，AI 仅提供辅助意见，请人工核对所有照片后再确认入库。"
        if llm_error:
            message = (
                f"LLM 调用失败：{llm_error}。"
                "多张图片存在药品名称、生产企业或规格识别不一致，请人工核对所有照片后再确认入库。"
            )

        return MultiImageConsistencyResult(
            status="review_required",
            method="llm_soft_conflict" if llm_judgement or llm_error else "rule_soft_conflict",
            review_required=True,
            batch_confirm_allowed=False,
            message=message,
            conflicts=soft_conflicts,
            merged_fields=merged_fields,
            merged_from_image_indexes=sources,
            raw_text=raw_text,
            llm_judgement=asdict(llm_judgement) if llm_judgement else None,
            llm_error=llm_error,
        )

    if _has_consistent_anchor(values):
        return MultiImageConsistencyResult(
            status="passed",
            method="rule_anchor",
            review_required=False,
            batch_confirm_allowed=True,
            message="多张图片存在可交叉验证的一致字段，请核对后确认入库。",
            conflicts=conflicts,
            merged_fields=merged_fields,
            merged_from_image_indexes=sources,
            raw_text=raw_text,
        )

    if llm_judgement and (llm_judgement.decision == "fail" or llm_judgement.same_drug == "unlikely"):
        return MultiImageConsistencyResult(
            status="failed",
            method="llm_no_overlap",
            review_required=False,
            batch_confirm_allowed=False,
            message=llm_judgement.reason or "AI 辅助判断疑似不是同一药品。",
            conflicts=conflicts,
            merged_fields=merged_fields,
            merged_from_image_indexes=sources,
            raw_text=raw_text,
            llm_judgement=asdict(llm_judgement),
        )

    message = "多张图片缺少可交叉验证字段，AI 仅提供辅助意见，请人工核对所有照片后再确认入库。"
    if llm_error:
        message = f"LLM 调用失败：{llm_error}。请人工核对所有照片后再确认入库。"

    return MultiImageConsistencyResult(
        status="review_required",
        method="llm_no_overlap" if llm_judgement or llm_error else "rule_no_overlap",
        review_required=True,
        batch_confirm_allowed=False,
        message=message,
        conflicts=conflicts,
        merged_fields=merged_fields,
        merged_from_image_indexes=sources,
        raw_text=raw_text,
        llm_judgement=asdict(llm_judgement) if llm_judgement else None,
        llm_error=llm_error,
    )
