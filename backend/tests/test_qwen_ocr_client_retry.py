from app.ocr import qwen_ocr_client


async def test_recognize_drug_retries_transport_disconnect(monkeypatch):
    monkeypatch.setattr(qwen_ocr_client.settings, "dashscope_api_key", "test-key")
    monkeypatch.setattr(qwen_ocr_client.settings, "qwen_ocr_max_attempts", 2)

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": '{"raw_text": "OK", "name": "Test Drug"}',
                        },
                    },
                ],
            }

    class FakeAsyncClient:
        attempts = 0

        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, *args, **kwargs):
            FakeAsyncClient.attempts += 1
            if FakeAsyncClient.attempts == 1:
                raise qwen_ocr_client.httpx.RemoteProtocolError(
                    "Server disconnected without sending a response."
                )
            return FakeResponse()

    monkeypatch.setattr(qwen_ocr_client.httpx, "AsyncClient", FakeAsyncClient)

    result = await qwen_ocr_client.recognize_drug(b"image")

    assert FakeAsyncClient.attempts == 2
    assert result["raw_text"] == "OK"
    assert result["fields"]["name"] == "Test Drug"


async def test_recognize_drug_stops_at_configured_attempts(monkeypatch):
    monkeypatch.setattr(qwen_ocr_client.settings, "dashscope_api_key", "test-key")
    monkeypatch.setattr(qwen_ocr_client.settings, "qwen_ocr_max_attempts", 1)

    class FakeAsyncClient:
        attempts = 0

        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, *args, **kwargs):
            FakeAsyncClient.attempts += 1
            raise qwen_ocr_client.httpx.ConnectTimeout("slow")

    monkeypatch.setattr(qwen_ocr_client.httpx, "AsyncClient", FakeAsyncClient)

    try:
        await qwen_ocr_client.recognize_drug(b"image")
    except RuntimeError as exc:
        assert "slow" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")

    assert FakeAsyncClient.attempts == 1
