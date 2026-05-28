"""Upload OCR images to Aliyun OSS and return temporary signed URLs."""

import uuid

from app.config import settings


def _load_oss2():
    try:
        import oss2  # type: ignore
    except ImportError as exc:
        raise RuntimeError("未安装 oss2，无法上传 OCR 图片到阿里云 OSS") from exc
    return oss2


def _missing_config_keys() -> list[str]:
    required = {
        "ALIYUN_OSS_ENDPOINT": settings.aliyun_oss_endpoint,
        "ALIYUN_OSS_BUCKET": settings.aliyun_oss_bucket,
        "ALIYUN_OSS_ACCESS_KEY_ID": settings.aliyun_oss_access_key_id,
        "ALIYUN_OSS_ACCESS_KEY_SECRET": settings.aliyun_oss_access_key_secret,
    }
    return [key for key, value in required.items() if not str(value or "").strip()]


def _require_config() -> None:
    missing = _missing_config_keys()
    if missing:
        raise RuntimeError(
            "未配置阿里云 OSS OCR 临时签名 URL，缺少：" + ", ".join(missing)
        )


def _normalized_prefix() -> str:
    return str(settings.aliyun_oss_ocr_prefix or "").strip().strip("/")


def _object_key() -> str:
    filename = f"{uuid.uuid4().hex}.jpg"
    prefix = _normalized_prefix()
    return f"{prefix}/{filename}" if prefix else filename


def _signed_url_expires() -> int:
    try:
        configured = int(settings.aliyun_oss_signed_url_expire_seconds)
    except (TypeError, ValueError):
        configured = 1800
    return max(60, configured)


def _create_bucket():
    _require_config()
    oss2 = _load_oss2()
    auth = oss2.Auth(
        settings.aliyun_oss_access_key_id,
        settings.aliyun_oss_access_key_secret,
    )
    return oss2.Bucket(auth, settings.aliyun_oss_endpoint, settings.aliyun_oss_bucket)


def upload_image_and_sign_url(image_bytes: bytes) -> str:
    if not image_bytes:
        raise RuntimeError("OSS 上传图片为空，无法生成 OCR 临时签名 URL")

    _require_config()
    key = _object_key()
    bucket = _create_bucket()
    result = bucket.put_object(
        key,
        image_bytes,
        headers={"Content-Type": "image/jpeg"},
    )
    status = getattr(result, "status", 200)
    if status >= 400:
        raise RuntimeError(f"OSS 上传 OCR 图片失败，HTTP 状态码：{status}")

    return bucket.sign_url("GET", key, _signed_url_expires())
