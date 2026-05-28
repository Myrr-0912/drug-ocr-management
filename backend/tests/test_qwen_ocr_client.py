import base64

from app.ocr import qwen_ocr_client


def test_build_payload_embeds_image_and_pixels(monkeypatch):
    monkeypatch.setattr(qwen_ocr_client.settings, "qwen_ocr_model", "qwen-vl-ocr-latest")
    monkeypatch.setattr(qwen_ocr_client.settings, "qwen_ocr_max_pixels", 4194304)
    payload = qwen_ocr_client._build_payload(b"hello")
    assert payload["model"] == "qwen-vl-ocr-latest"
    content = payload["messages"][0]["content"]
    image_part = next(p for p in content if p["type"] == "image_url")
    assert base64.b64encode(b"hello").decode("ascii") in image_part["image_url"]["url"]
    assert image_part["min_pixels"] == 3072
    assert image_part["max_pixels"] == 4194304


async def test_recognize_drug_uses_configured_timeout(monkeypatch):
    monkeypatch.setattr(qwen_ocr_client.settings, "dashscope_api_key", "test-key")
    monkeypatch.setattr(qwen_ocr_client.settings, "qwen_ocr_timeout_seconds", 37)
    monkeypatch.setattr(qwen_ocr_client.settings, "qwen_ocr_max_attempts", 1)

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
            return FakeResponse()

    monkeypatch.setattr(qwen_ocr_client.httpx, "AsyncClient", FakeAsyncClient)

    await qwen_ocr_client.recognize_drug(b"image")

    assert seen["timeout"] == 37


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


async def test_recognize_drug_mock_when_no_key(monkeypatch):
    monkeypatch.setattr(qwen_ocr_client.settings, "dashscope_api_key", "")
    result = await qwen_ocr_client.recognize_drug(b"image")
    assert result["fields"]["name"] == "阿莫西林胶囊"
    assert "阿莫西林胶囊" in result["raw_text"]
