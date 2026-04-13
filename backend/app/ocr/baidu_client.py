"""
百度 OCR API 客户端
- 若 .env 中配置了 baidu_ocr_api_key / secret_key，则调用真实 API
- 否则自动切换为 mock 模式，返回预设测试数据，方便本地开发
"""
import base64
import time
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# 百度 API 基础 URL
_TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
_OCR_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/accurate_basic"

# 简单内存缓存 access_token（避免每次请求都重新获取）
_cached_token: str | None = None
_token_expires_at: float = 0.0


async def _get_access_token() -> str:
    """获取百度 API access_token，带过期自动刷新"""
    global _cached_token, _token_expires_at

    if _cached_token and time.time() < _token_expires_at - 60:
        return _cached_token

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            _TOKEN_URL,
            params={
                "grant_type": "client_credentials",
                "client_id": settings.baidu_ocr_api_key,
                "client_secret": settings.baidu_ocr_secret_key,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"百度 Token 获取失败: {data.get('error_description', data['error'])}")

        _cached_token = data["access_token"]
        _token_expires_at = time.time() + data.get("expires_in", 2592000)
        return _cached_token


async def recognize_image(image_bytes: bytes) -> dict:
    """
    调用百度 OCR 识别图片文字，返回：
    {
        "raw_text": "完整识别文本",
        "words_result": [...],   # 原始词条列表
        "confidence": 0.95,
    }
    """
    # 未配置 API Key → mock 模式
    if not settings.baidu_ocr_api_key or not settings.baidu_ocr_secret_key:
        logger.warning("百度 OCR API Key 未配置，使用 mock 模式")
        return _mock_response()

    try:
        token = await _get_access_token()
        image_b64 = base64.b64encode(image_bytes).decode()

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                _OCR_URL,
                params={"access_token": token},
                data={"image": image_b64, "language_type": "CHN_ENG"},
            )
            resp.raise_for_status()
            data = resp.json()

        if "error_code" in data:
            raise RuntimeError(f"百度 OCR 识别失败 [{data['error_code']}]: {data.get('error_msg', '')}")

        words_result = data.get("words_result", [])
        raw_text = "\n".join(item["words"] for item in words_result)

        # 百度高精度接口不直接返回置信度，用词条数量作为粗略质量指标
        confidence = min(1.0, len(words_result) / 20.0) if words_result else 0.0

        return {
            "raw_text": raw_text,
            "words_result": words_result,
            "confidence": round(confidence, 2),
        }

    except httpx.HTTPError as e:
        raise RuntimeError(f"HTTP 请求失败: {e}") from e


def _mock_response() -> dict:
    """开发用 mock 响应，模拟真实药品说明书 OCR 结果"""
    mock_words = [
        {"words": "阿莫西林胶囊"},
        {"words": "通用名：阿莫西林胶囊"},
        {"words": "批准文号：国药准字H20044416"},
        {"words": "规格：0.25g×24粒"},
        {"words": "生产企业：广州白云山制药股份有限公司"},
        {"words": "批号：20240315"},
        {"words": "生产日期：20240315"},
        {"words": "有效期至：2026年03月"},
        {"words": "贮藏：密封，在干燥处保存"},
        {"words": "执行标准：WS1-XG-022-2000-2018"},
    ]
    raw_text = "\n".join(item["words"] for item in mock_words)
    return {
        "raw_text": raw_text,
        "words_result": mock_words,
        "confidence": 0.92,
    }
