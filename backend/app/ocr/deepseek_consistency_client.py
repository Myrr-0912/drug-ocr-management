"""DeepSeek 多图 OCR 一致性辅助校验客户端。"""

from __future__ import annotations

import json
import logging
import re

import httpx

from app.config import settings
from app.ocr.multi_image_consistency import ImageOcrEvidence, LlmConsistencyJudgement

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """你是药品包装 OCR 结果的一致性辅助审核器。
你的任务是判断多张图片的 OCR 文本是否可能来自同一种药品盒子的不同包装面。
你只能依据输入中的 OCR 文本和字段判断，不要编造任何没有出现的信息。
你只是辅助判断，不能替代人工审核。
如果证据不足，请返回 uncertain/review。
只输出 JSON，不要输出额外说明。"""


def _build_payload(evidence: list[ImageOcrEvidence]) -> dict:
    images = [
        {
            "image_index": item.image_index,
            "raw_text": item.raw_text,
            "fields": item.fields,
        }
        for item in evidence
    ]
    user_content = {
        "task": "判断这些 OCR 文本是否可能来自同一种药品盒子的不同包装面",
        "rules": [
            "你只是辅助判断，不能替代人工审核",
            "如果证据不足，请返回 uncertain",
            "不要编造图片中没有出现的信息",
            "发现疑似不同药品、不同规格、不同厂家、不同批次时要指出",
        ],
        "images": images,
        "output_schema": {
            "same_drug": "likely | unlikely | uncertain",
            "confidence": "0 到 1 的数字",
            "decision": "pass | review | fail",
            "reason": "简短中文原因",
            "evidence": ["支持判断的 OCR 证据"],
            "risk_notes": ["需要人工关注的风险点"],
        },
    }
    return {
        "model": settings.deepseek_model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(user_content, ensure_ascii=False)},
        ],
        "temperature": 0,
    }


def _fallback_judgement(reason: str) -> LlmConsistencyJudgement:
    return LlmConsistencyJudgement(
        same_drug="uncertain",
        confidence=0,
        decision="review",
        reason=reason,
        evidence=[],
        risk_notes=["AI 辅助判断不可用，请人工核对"],
    )


def _parse_judgement(resp_json: dict) -> LlmConsistencyJudgement:
    try:
        content = resp_json["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        logger.warning("[DeepSeekConsistency] 响应结构异常：%s", resp_json)
        return _fallback_judgement("DeepSeek 响应结构异常，无法解析辅助判断")

    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", str(content), re.DOTALL)
    raw = fenced.group(1) if fenced else str(content)
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        logger.warning("[DeepSeekConsistency] 输出非合法 JSON：%s", content)
        return _fallback_judgement("DeepSeek 输出解析失败，请人工审核")

    if not isinstance(parsed, dict):
        return _fallback_judgement("DeepSeek 输出不是 JSON 对象，请人工审核")

    same_drug = parsed.get("same_drug")
    if same_drug not in {"likely", "unlikely", "uncertain"}:
        same_drug = "uncertain"
    decision = parsed.get("decision")
    if decision not in {"pass", "review", "fail"}:
        decision = "review"
    try:
        confidence = float(parsed.get("confidence", 0))
    except (TypeError, ValueError):
        confidence = 0
    confidence = max(0, min(1, confidence))

    evidence = parsed.get("evidence")
    risk_notes = parsed.get("risk_notes")
    return LlmConsistencyJudgement(
        same_drug=same_drug,
        confidence=confidence,
        decision=decision,
        reason=str(parsed.get("reason") or "DeepSeek 未提供明确原因，请人工审核"),
        evidence=evidence if isinstance(evidence, list) else [],
        risk_notes=risk_notes if isinstance(risk_notes, list) else [],
    )


async def judge_same_drug(evidence: list[ImageOcrEvidence]) -> LlmConsistencyJudgement:
    """调用 DeepSeek 判断无重叠字段的多图 OCR 文本是否可能属于同一药品。"""
    if not settings.deepseek_api_key:
        raise RuntimeError("未配置 DEEPSEEK_API_KEY，无法进行多图一致性辅助校验")

    base_url = settings.deepseek_base_url.rstrip("/")
    async with httpx.AsyncClient(timeout=max(1, settings.deepseek_timeout_seconds)) as client:
        resp = await client.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.deepseek_api_key}",
                "Content-Type": "application/json",
            },
            json=_build_payload(evidence),
        )
    resp.raise_for_status()
    return _parse_judgement(resp.json())
