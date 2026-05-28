"""
通义千问 OCR 客户端 — 阿里云百炼 qwen-vl-ocr-latest

走百炼 OpenAI 兼容接口，一次调用产出图像完整文本 raw_text 与模型抽取的结构化字段。
未配置 DASHSCOPE_API_KEY 或 API/网络异常时抛 RuntimeError 交由上层处理。
"""
import asyncio
import json
import logging
import re

import httpx

from app.config import settings
from app.ocr.oss_image_store import upload_image_and_sign_url

logger = logging.getLogger(__name__)

# 阿里云百炼 OpenAI 兼容端点
_BAILIAN_ENDPOINT = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

# qwen-vl-ocr 图像像素范围（清晰度与 token 消耗的权衡）
_MIN_PIXELS = 3072
_RETRY_BACKOFF_SECONDS = 0.5
_GLOBAL_CONCURRENCY_HARD_LIMIT = 5
_global_ocr_semaphore: asyncio.Semaphore | None = None
_global_ocr_semaphore_limit: int | None = None

# 需要模型抽取的结构化字段
_DRUG_FIELDS = (
    "name", "approval_number", "manufacturer", "specification",
    "batch_number", "production_date", "expiry_date", "quantity",
)

# 提示词：要求模型同时输出完整文本与结构化字段
_OCR_PROMPT = """请识别这张药品包装图片，完成两件事并只输出一个 JSON 对象：

1. raw_text：图片中识别到的全部文字，尽量完整保留原始换行和字段标签。
2. 提取以下字段，无法确定的填 null，禁止编造，禁止根据常识补全。

字段定义与提取规则：
- name：药品名称/通用名称。优先从“药品名称”“通用名称”字段后提取；如果图片标题是“xxx说明书”，提取 xxx，去掉“说明书”。不要把商标、Logo、品牌简称、企业简称当作药品名称，例如包装角落或顶部单独出现的品牌字样不能作为 name。
- approval_number：批准文号，必须是“国药准字”+1位字母+8位数字，例如“国药准字Z10970018”。不符合格式填 null。
- manufacturer：生产企业或上市许可持有人全称，优先提取带“生产企业”“生产厂家”“上市许可持有人及生产企业”“企业名称”等标签后的公司全称。不要填品牌简称。
- specification：规格，按图片原文提取，例如“7厘米×10厘米”“每1毫升相当于饮片0.27克”等。
- batch_number：批号/产品批号/生产批号/Lot No.，必须优先从“批号”“产品批号”“生产批号”“Lot No.”附近提取。不要把商品条形码、追溯码、监管码、二维码数字填为批号；13位纯数字且位于条形码下方时通常不是批号。
- production_date：生产日期，统一输出 YYYY-MM-DD；如果只有年月，日期填 01。
- expiry_date：有效期至，统一输出 YYYY-MM-DD；如果只有年月，日期填 01。
- quantity：数量，整数；无法确定填 null。

特别注意：
- name 不能是厂家简称、品牌名或 Logo 文本。
- batch_number 不能是条形码数字。
- 如果字段附近没有明确标签或无法判断，请填 null。
- 输出必须是合法 JSON，不要 Markdown，不要解释文字。

输出格式：
{"raw_text": "...", "name": null, "approval_number": null, "manufacturer": null, "specification": null, "batch_number": null, "production_date": null, "expiry_date": null, "quantity": null}
"""


def _build_payload(image_url: str) -> dict:
    """构造百炼 chat/completions 请求体，图片统一使用 OSS 临时签名 URL"""
    return {
        "model": settings.qwen_ocr_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": image_url},
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


def _bounded_concurrency(value, default: int, hard_limit: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return min(max(1, parsed), hard_limit)


def _get_global_ocr_semaphore() -> asyncio.Semaphore:
    global _global_ocr_semaphore, _global_ocr_semaphore_limit
    limit = _bounded_concurrency(
        settings.qwen_ocr_global_concurrency,
        default=3,
        hard_limit=_GLOBAL_CONCURRENCY_HARD_LIMIT,
    )
    if _global_ocr_semaphore is None or _global_ocr_semaphore_limit != limit:
        _global_ocr_semaphore = asyncio.Semaphore(limit)
        _global_ocr_semaphore_limit = limit
    return _global_ocr_semaphore


async def recognize_drug(image_bytes: bytes) -> dict:
    """
    调用 qwen-vl-ocr-latest 识别药盒图片。
    返回 {"raw_text": str, "fields": dict}。
    未配置 DASHSCOPE_API_KEY 或 API/网络异常 → RuntimeError。
    """
    if not settings.dashscope_api_key:
        raise RuntimeError("未配置 DASHSCOPE_API_KEY，无法调用 qwen-vl-ocr 进行真实 OCR 识别")

    image_url = await asyncio.to_thread(upload_image_and_sign_url, image_bytes)
    payload = _build_payload(image_url)
    max_attempts = max(1, settings.qwen_ocr_max_attempts)
    timeout_seconds = max(1, settings.qwen_ocr_timeout_seconds)

    for attempt in range(1, max_attempts + 1):
        try:
            async with _get_global_ocr_semaphore():
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
