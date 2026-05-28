"""
通义千问 OCR 客户端 — 阿里云百炼 qwen-vl-ocr-latest

走百炼 OpenAI 兼容接口，一次调用产出图像完整文本 raw_text 与模型抽取的结构化字段。
未配置 DASHSCOPE_API_KEY 时返回 mock 数据；API/网络异常抛 RuntimeError 交由上层处理。
"""
import base64
import asyncio
import json
import logging
import re

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# 阿里云百炼 OpenAI 兼容端点
_BAILIAN_ENDPOINT = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

# qwen-vl-ocr 图像像素范围（清晰度与 token 消耗的权衡）
_MIN_PIXELS = 3072
_RETRY_BACKOFF_SECONDS = 0.5

# 需要模型抽取的结构化字段
_DRUG_FIELDS = (
    "name", "approval_number", "manufacturer", "specification",
    "batch_number", "production_date", "expiry_date", "quantity",
)

# 提示词：要求模型同时输出完整文本与结构化字段
_OCR_PROMPT = """请识别这张药品包装图片，完成两件事并只输出一个 JSON 对象：
1. raw_text：图片中识别到的全部文字（保留换行）。
2. 提取以下字段，无法确定的填 null，禁止编造：
   name（药品通用名称）、approval_number（批准文号，如 国药准字H20044416）、
   manufacturer（生产企业全称）、specification（规格，如 0.25g×24粒）、
   batch_number（批号）、production_date（生产日期 YYYY-MM-DD）、
   expiry_date（有效期至 YYYY-MM-DD）、quantity（数量，整数）。
输出格式：{"raw_text": "...", "name": null, "approval_number": null, "manufacturer": null, "specification": null, "batch_number": null, "production_date": null, "expiry_date": null, "quantity": null}
只输出 JSON，不要任何额外说明文字。"""


def _build_payload(image_bytes: bytes) -> dict:
    """构造百炼 chat/completions 请求体，图片以 base64 data URL 内联"""
    b64 = base64.b64encode(image_bytes).decode("ascii")
    data_url = f"data:image/jpeg;base64,{b64}"
    return {
        "model": settings.qwen_ocr_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": data_url},
                        "min_pixels": _MIN_PIXELS,
                        "max_pixels": settings.qwen_ocr_max_pixels,
                    },
                    {"type": "text", "text": _OCR_PROMPT},
                ],
            },
        ],
        "temperature": 0.01,
    }


def _parse_response(resp_json: dict) -> dict:
    """
    从百炼响应取出模型输出，解析为 {"raw_text": str, "fields": dict}。
    JSON 解析失败时把整段输出当作 raw_text，fields 留空交由正则兜底。
    """
    try:
        content = resp_json["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        logger.error("[QwenOCR] 响应结构异常：%s", resp_json)
        return {"raw_text": "", "fields": {}}

    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", content, re.DOTALL)
    raw = fenced.group(1) if fenced else content
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        logger.warning("[QwenOCR] 输出非合法 JSON，整段作为 raw_text 交由正则兜底")
        return {"raw_text": content if isinstance(content, str) else "", "fields": {}}

    if not isinstance(parsed, dict):
        return {"raw_text": content if isinstance(content, str) else "", "fields": {}}

    raw_text = parsed.get("raw_text") or ""
    fields = {f: parsed.get(f) for f in _DRUG_FIELDS}
    return {"raw_text": str(raw_text), "fields": fields}


def _mock_response() -> dict:
    """开发用 mock 响应，模拟 qwen-vl-ocr 输出"""
    raw_text = "\n".join([
        "阿莫西林胶囊",
        "批准文号：国药准字H20044416",
        "规格：0.25g×24粒",
        "生产企业：广州白云山制药股份有限公司",
        "批号：20240315",
        "生产日期：2024-03-15",
        "有效期至：2026-03-01",
    ])
    return {
        "raw_text": raw_text,
        "fields": {
            "name": "阿莫西林胶囊",
            "approval_number": "国药准字H20044416",
            "manufacturer": "广州白云山制药股份有限公司",
            "specification": "0.25g×24粒",
            "batch_number": "20240315",
            "production_date": "2024-03-15",
            "expiry_date": "2026-03-01",
            "quantity": None,
        },
    }


async def recognize_drug(image_bytes: bytes) -> dict:
    """
    调用 qwen-vl-ocr-latest 识别药盒图片。
    返回 {"raw_text": str, "fields": dict}。
    未配置 DASHSCOPE_API_KEY → 返回 mock；API/网络异常 → RuntimeError。
    """
    if not settings.dashscope_api_key:
        logger.warning("[QwenOCR] 未配置 DASHSCOPE_API_KEY，使用 mock 模式")
        return _mock_response()

    payload = _build_payload(image_bytes)
    max_attempts = max(1, settings.qwen_ocr_max_attempts)
    timeout_seconds = max(1, settings.qwen_ocr_timeout_seconds)

    for attempt in range(1, max_attempts + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                resp = await client.post(
                    _BAILIAN_ENDPOINT,
                    headers={
                        "Authorization": f"Bearer {settings.dashscope_api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
            resp.raise_for_status()
            return _parse_response(resp.json())
        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"qwen-vl-ocr 调用失败 [{e.response.status_code}]: {e.response.text}"
            ) from e
        except httpx.TransportError as e:
            if attempt >= max_attempts:
                raise RuntimeError(f"qwen-vl-ocr 请求异常: {e}") from e
            logger.warning(
                "[QwenOCR] transport error on attempt %s/%s, retrying: %s",
                attempt,
                max_attempts,
                e,
            )
            await asyncio.sleep(_RETRY_BACKOFF_SECONDS * attempt)
        except Exception as e:
            raise RuntimeError(f"qwen-vl-ocr 请求异常: {e}") from e

    raise RuntimeError("qwen-vl-ocr 请求异常: exceeded retry attempts")
