import asyncio

import pytest

from app.ocr import qwen_ocr_client


def test_ocr_prompt_does_not_contain_concrete_fake_field_examples():
    assert "H20044416" not in qwen_ocr_client._OCR_PROMPT
    assert "0.25g" not in qwen_ocr_client._OCR_PROMPT


def test_build_payload_uses_signed_image_url_and_pixels(monkeypatch):
    monkeypatch.setattr(qwen_ocr_client.settings, "qwen_ocr_model", "qwen-vl-ocr-latest")
    monkeypatch.setattr(qwen_ocr_client.settings, "qwen_ocr_max_pixels", 4194304)
    image_url = "https://oss.example.test/ocr/qwen/image.jpg?Expires=1800&Signature=test"
    payload = qwen_ocr_client._build_payload(image_url)
    assert payload["model"] == "qwen-vl-ocr-latest"
    content = payload["messages"][0]["content"]
    image_part = next(p for p in content if p["type"] == "image_url")
    assert image_part["image_url"]["url"] == image_url
    assert not image_part["image_url"]["url"].startswith("data:image/")
    assert image_part["min_pixels"] == 3072
    assert image_part["max_pixels"] == 4194304


async def test_recognize_drug_uses_configured_timeout(monkeypatch):
    monkeypatch.setattr(qwen_ocr_client.settings, "dashscope_api_key", "test-key")
    monkeypatch.setattr(qwen_ocr_client.settings, "qwen_ocr_timeout_seconds", 37)
    monkeypatch.setattr(qwen_ocr_client.settings, "qwen_ocr_max_attempts", 1)
    monkeypatch.setattr(
        qwen_ocr_client,
        "upload_image_and_sign_url",
        lambda image_bytes: "https://oss.example.test/ocr/qwen/image.jpg?Signature=test",
        raising=False,
    )

    seen = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": '{"raw_text": "OK"}'}}]}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            seen["timeout"] = kwargs["timeout"]

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, *args, **kwargs):
            content = kwargs["json"]["messages"][0]["content"]
            image_part = next(p for p in content if p["type"] == "image_url")
            seen["image_url"] = image_part["image_url"]["url"]
            return FakeResponse()

    monkeypatch.setattr(qwen_ocr_client.httpx, "AsyncClient", FakeAsyncClient)

    await qwen_ocr_client.recognize_drug(b"image")

    assert seen["timeout"] == 37
    assert seen["image_url"].startswith("https://oss.example.test/")
    assert "base64" not in seen["image_url"]


async def test_recognize_drug_limits_global_concurrency(monkeypatch):
    monkeypatch.setattr(qwen_ocr_client.settings, "dashscope_api_key", "test-key")
    monkeypatch.setattr(qwen_ocr_client.settings, "qwen_ocr_max_attempts", 1)
    monkeypatch.setattr(qwen_ocr_client.settings, "qwen_ocr_global_concurrency", 3, raising=False)
    monkeypatch.setattr(
        qwen_ocr_client,
        "upload_image_and_sign_url",
        lambda image_bytes: "https://oss.example.test/ocr/qwen/image.jpg?Signature=test",
        raising=False,
    )

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": '{"raw_text": "OK"}'}}]}

    class FakeAsyncClient:
        active = 0
        max_active = 0

        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, *args, **kwargs):
            FakeAsyncClient.active += 1
            FakeAsyncClient.max_active = max(FakeAsyncClient.max_active, FakeAsyncClient.active)
            await asyncio.sleep(0.01)
            FakeAsyncClient.active -= 1
            return FakeResponse()

    monkeypatch.setattr(qwen_ocr_client.httpx, "AsyncClient", FakeAsyncClient)

    await asyncio.gather(*(qwen_ocr_client.recognize_drug(b"image") for _ in range(5)))

    assert FakeAsyncClient.max_active == 3


def test_parse_response_plain_json():
    resp = {"choices": [{"message": {"content":
        '{"raw_text": "药盒文本", "name": "阿莫西林胶囊", "batch_number": "20240315"}'}}]}
    result = qwen_ocr_client._parse_response(resp)
    assert result["raw_text"] == "药盒文本"
    assert result["fields"]["name"] == "阿莫西林胶囊"
    assert result["fields"]["batch_number"] == "20240315"
    assert result["fields"]["quantity"] is None


def test_parse_response_fenced_json():
    resp = {"choices": [{"message": {"content":
        '```json\n{"raw_text": "T", "name": "测试药"}\n```'}}]}
    result = qwen_ocr_client._parse_response(resp)
    assert result["raw_text"] == "T"
    assert result["fields"]["name"] == "测试药"


def test_parse_response_invalid_json_falls_back_to_raw_text():
    resp = {"choices": [{"message": {"content": "阿莫西林胶囊 批号20240315"}}]}
    result = qwen_ocr_client._parse_response(resp)
    assert result["raw_text"] == "阿莫西林胶囊 批号20240315"
    assert result["fields"] == {}


def test_parse_response_bad_structure():
    result = qwen_ocr_client._parse_response({"unexpected": "shape"})
    assert result == {"raw_text": "", "fields": {}}


async def test_recognize_drug_requires_api_key(monkeypatch):
    monkeypatch.setattr(qwen_ocr_client.settings, "dashscope_api_key", "")

    with pytest.raises(RuntimeError, match="DASHSCOPE_API_KEY"):
        await qwen_ocr_client.recognize_drug(b"image")
