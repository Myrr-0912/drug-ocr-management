import cv2
import numpy as np

from app.ocr import image_preprocess
from app.ocr.image_preprocess import preprocess_image


def _make_jpeg(width: int, height: int) -> bytes:
    """生成一张带简单图案的 JPEG 测试图"""
    arr = np.full((height, width, 3), 255, dtype=np.uint8)
    cv2.rectangle(arr, (10, 10), (width - 10, height - 10), (0, 0, 0), 3)
    ok, buf = cv2.imencode(".jpg", arr)
    assert ok
    return buf.tobytes()


def test_preprocess_returns_decodable_jpeg():
    out = preprocess_image(_make_jpeg(1200, 900))
    decoded = cv2.imdecode(np.frombuffer(out, np.uint8), cv2.IMREAD_COLOR)
    assert decoded is not None


def test_preprocess_upscales_small_image():
    out = preprocess_image(_make_jpeg(400, 300))
    decoded = cv2.imdecode(np.frombuffer(out, np.uint8), cv2.IMREAD_COLOR)
    assert min(decoded.shape[:2]) >= 1000


def test_preprocess_uses_configured_target_short_edge(monkeypatch):
    monkeypatch.setattr(image_preprocess.settings, "ocr_preprocess_min_short_edge", 400)
    monkeypatch.setattr(image_preprocess.settings, "ocr_preprocess_target_short_edge", 900)

    out = preprocess_image(_make_jpeg(300, 200))
    decoded = cv2.imdecode(np.frombuffer(out, np.uint8), cv2.IMREAD_COLOR)

    assert min(decoded.shape[:2]) >= 900


def test_preprocess_garbage_bytes_returns_original():
    garbage = b"this is not an image"
    assert preprocess_image(garbage) == garbage
