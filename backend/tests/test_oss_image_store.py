import pytest

from app.ocr import oss_image_store


def test_upload_image_and_sign_url_requires_oss_config(monkeypatch):
    monkeypatch.setattr(oss_image_store.settings, "aliyun_oss_endpoint", "")
    monkeypatch.setattr(oss_image_store.settings, "aliyun_oss_bucket", "")
    monkeypatch.setattr(oss_image_store.settings, "aliyun_oss_access_key_id", "")
    monkeypatch.setattr(oss_image_store.settings, "aliyun_oss_access_key_secret", "")

    with pytest.raises(RuntimeError, match="OSS"):
        oss_image_store.upload_image_and_sign_url(b"image")


def test_upload_image_and_sign_url_uploads_and_signs(monkeypatch):
    monkeypatch.setattr(oss_image_store.settings, "aliyun_oss_endpoint", "oss-cn-test.aliyuncs.com")
    monkeypatch.setattr(oss_image_store.settings, "aliyun_oss_bucket", "drug-ocr")
    monkeypatch.setattr(oss_image_store.settings, "aliyun_oss_access_key_id", "ak")
    monkeypatch.setattr(oss_image_store.settings, "aliyun_oss_access_key_secret", "sk")
    monkeypatch.setattr(oss_image_store.settings, "aliyun_oss_ocr_prefix", "ocr/qwen")
    monkeypatch.setattr(oss_image_store.settings, "aliyun_oss_signed_url_expire_seconds", 900)

    seen = {}

    class FakeBucket:
        def put_object(self, key, body, headers=None):
            seen["key"] = key
            seen["body"] = body
            seen["headers"] = headers

        def sign_url(self, method, key, expires):
            seen["method"] = method
            seen["signed_key"] = key
            seen["expires"] = expires
            return f"https://drug-ocr.oss-cn-test.aliyuncs.com/{key}?Signature=test"

    monkeypatch.setattr(oss_image_store, "_create_bucket", lambda: FakeBucket())
    monkeypatch.setattr(oss_image_store.uuid, "uuid4", lambda: type("Uuid", (), {"hex": "abc123"})())

    url = oss_image_store.upload_image_and_sign_url(b"image")

    assert url == "https://drug-ocr.oss-cn-test.aliyuncs.com/ocr/qwen/abc123.jpg?Signature=test"
    assert seen["key"] == "ocr/qwen/abc123.jpg"
    assert seen["body"] == b"image"
    assert seen["headers"] == {"Content-Type": "image/jpeg"}
    assert seen["method"] == "GET"
    assert seen["signed_key"] == "ocr/qwen/abc123.jpg"
    assert seen["expires"] == 900
