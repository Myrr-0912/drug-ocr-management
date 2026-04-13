"""
阿里云 OCR 文字识别客户端
- 使用 alibabacloud_ocr_api20210707 SDK（RecognizeGeneral 通用文字识别）
- SDK 为同步阻塞，通过 run_in_executor 包装为异步非阻塞
- 未配置 AccessKey 时自动切换 mock 模式，方便本地开发
"""
import asyncio
import io
import json
import logging
from concurrent.futures import ThreadPoolExecutor

from alibabacloud_ocr_api20210707.client import Client as OcrClient
from alibabacloud_ocr_api20210707.models import RecognizeGeneralRequest
from alibabacloud_tea_openapi.models import Config
from Tea.exceptions import TeaException

from app.config import settings

logger = logging.getLogger(__name__)

# 线程池：阿里云 SDK 是同步阻塞，最多 3 个并发 OCR 请求
_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="aliyun-ocr")

# 阿里云 OCR 服务端点（通用文字识别，杭州区域）
_OCR_ENDPOINT = "ocr-api.cn-hangzhou.aliyuncs.com"


def _create_client() -> OcrClient:
    """创建阿里云 OCR 客户端实例"""
    config = Config(
        access_key_id=settings.aliyun_ocr_access_key_id,
        access_key_secret=settings.aliyun_ocr_access_key_secret,
        endpoint=_OCR_ENDPOINT,
    )
    return OcrClient(config)


def _recognize_sync(image_bytes: bytes) -> dict:
    """
    同步调用阿里云 RecognizeGeneral 接口
    返回格式与原百度客户端保持一致，供 ocr_service 无缝使用：
    {
        "raw_text": "识别的完整文本",
        "words_result": [{"words": "..."}],
        "confidence": 0.95,
    }
    """
    client = _create_client()
    request = RecognizeGeneralRequest(body=io.BytesIO(image_bytes))
    response = client.recognize_general(request)

    # response.body.data 是 JSON 字符串，需要手动解析
    raw_data_str = response.body.data if response.body and response.body.data else "{}"
    data = json.loads(raw_data_str)

    raw_text = data.get("content", "")

    # 解析词条列表及置信度（字段名为 prism_wordsInfo）
    words_result = []
    prob_sum = 0.0
    prob_count = 0

    prism_info = data.get("prism_wordsInfo", [])
    for item in prism_info:
        word = item.get("word", "")
        if word:
            words_result.append({"words": word})
        # prob 范围 0–1000，换算为 0.0–1.0
        prob = item.get("prob")
        if prob is not None:
            prob_sum += prob / 1000.0
            prob_count += 1

    confidence = round(prob_sum / prob_count, 2) if prob_count > 0 else (
        min(1.0, round(len(words_result) / 20.0, 2)) if words_result else 0.0
    )

    return {
        "raw_text": raw_text,
        "words_result": words_result,
        "confidence": confidence,
    }


async def recognize_image(image_bytes: bytes) -> dict:
    """
    异步 OCR 入口，供 ocr_service 调用。
    - 有 AccessKey → 调用阿里云真实接口
    - 无 AccessKey → 返回 mock 数据（开发用）
    """
    if not settings.aliyun_ocr_access_key_id or not settings.aliyun_ocr_access_key_secret:
        logger.warning("阿里云 OCR AccessKey 未配置，使用 mock 模式")
        return _mock_response()

    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, _recognize_sync, image_bytes)
    except TeaException as e:
        raise RuntimeError(f"阿里云 OCR 调用失败 [{e.code}]: {e.message}") from e
    except Exception as e:
        raise RuntimeError(f"OCR 请求异常: {e}") from e


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
