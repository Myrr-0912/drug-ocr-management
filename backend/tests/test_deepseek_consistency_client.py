import pytest

from app.ocr.multi_image_consistency import ImageOcrEvidence
from app.ocr import deepseek_consistency_client


def test_build_payload_sends_ocr_text_and_fields_not_images(monkeypatch):
    monkeypatch.setattr(deepseek_consistency_client.settings, "deepseek_model", "deepseek-v4-flash", raising=False)

    payload = deepseek_consistency_client._build_payload([
        ImageOcrEvidence(
            image_index=1,
            raw_text="真实 OCR 文本",
            fields={"name": "药品甲"},
        ),
    ])

    user_content = payload["messages"][1]["content"]
    assert payload["model"] == "deepseek-v4-flash"
    assert "真实 OCR 文本" in user_content
    assert '"fields": {"name": "药品甲"}' in user_content
    assert "image_url" not in user_content
    assert "base64" not in user_content


async def test_judge_consistency_requires_api_key(monkeypatch):
    monkeypatch.setattr(deepseek_consistency_client.settings, "deepseek_api_key", "", raising=False)

    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        await deepseek_consistency_client.judge_same_drug([
            ImageOcrEvidence(image_index=1, raw_text="真实 OCR 文本", fields={"name": "药品甲"}),
        ])


async def test_judge_consistency_uses_configured_model_and_parses_json(monkeypatch):
    monkeypatch.setattr(deepseek_consistency_client.settings, "deepseek_api_key", "test-key", raising=False)
    monkeypatch.setattr(deepseek_consistency_client.settings, "deepseek_base_url", "https://example.test", raising=False)
    monkeypatch.setattr(deepseek_consistency_client.settings, "deepseek_model", "deepseek-v4-flash", raising=False)
    monkeypatch.setattr(deepseek_consistency_client.settings, "deepseek_timeout_seconds", 11, raising=False)

    seen = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "choices": [{
                    "message": {
                        "content": (
                            '{"same_drug": "likely", "confidence": 0.7, "decision": "review", '
                            '"reason": "未发现冲突", "evidence": ["图片1"], "risk_notes": ["需人工审核"]}'
                        )
                    },
                }],
            }

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            seen["timeout"] = kwargs["timeout"]

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, *, headers, json):
            seen["url"] = url
            seen["headers"] = headers
            seen["json"] = json
            return FakeResponse()

    monkeypatch.setattr(deepseek_consistency_client.httpx, "AsyncClient", FakeAsyncClient)

    result = await deepseek_consistency_client.judge_same_drug([
        ImageOcrEvidence(image_index=1, raw_text="真实 OCR 文本", fields={"name": "药品甲"}),
    ])

    assert seen["timeout"] == 11
    assert seen["url"] == "https://example.test/chat/completions"
    assert seen["headers"]["Authorization"] == "Bearer test-key"
    assert seen["json"]["model"] == "deepseek-v4-flash"
    assert result.same_drug == "likely"
    assert result.decision == "review"
    assert result.risk_notes == ["需人工审核"]


async def test_judge_consistency_invalid_json_returns_uncertain_review(monkeypatch):
    monkeypatch.setattr(deepseek_consistency_client.settings, "deepseek_api_key", "test-key", raising=False)
    monkeypatch.setattr(deepseek_consistency_client.settings, "deepseek_base_url", "https://example.test", raising=False)
    monkeypatch.setattr(deepseek_consistency_client.settings, "deepseek_timeout_seconds", 11, raising=False)

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "不是 JSON"}}]}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(deepseek_consistency_client.httpx, "AsyncClient", FakeAsyncClient)

    result = await deepseek_consistency_client.judge_same_drug([
        ImageOcrEvidence(image_index=1, raw_text="真实 OCR 文本", fields={}),
    ])

    assert result.same_drug == "uncertain"
    assert result.decision == "review"
    assert "解析" in result.reason
