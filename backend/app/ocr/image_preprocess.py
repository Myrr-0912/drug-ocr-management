"""
图像预处理 — OCR 识别前的几何与质量优化

处理链：EXIF 方向修正 → 自动纠偏 → 分辨率放大 → 轻度对比度增强
任何异常均记录日志并返回原始字节，绝不影响主识别流程。
保留彩色、不做二值化（qwen-vl-ocr 在干净彩色图上表现最好）。
"""
import io
import logging

import cv2
import numpy as np
from PIL import Image, ImageOps

from app.config import settings

logger = logging.getLogger(__name__)

# 纠偏检测角度绝对值超过此值视为非倾斜噪声，不参与中位数
_MAX_DESKEW_ANGLE = 15.0


def _load_as_bgr(image_bytes: bytes) -> np.ndarray:
    """用 Pillow 解码并按 EXIF 标记旋正，转为 opencv 的 BGR ndarray"""
    pil_img = Image.open(io.BytesIO(image_bytes))
    pil_img = ImageOps.exif_transpose(pil_img)   # opencv 从字节流解码不读 EXIF，这里补上
    pil_img = pil_img.convert("RGB")
    rgb = np.array(pil_img)
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def _detect_skew_angle(gray: np.ndarray) -> float:
    """用霍夫直线检测主体倾斜角，返回需旋转校正的角度（度）。检测不到返回 0。"""
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLines(edges, 1, np.pi / 180, threshold=200)
    if lines is None:
        return 0.0
    angles = []
    for line in lines[:100]:
        _rho, theta = line[0]
        deg = np.degrees(theta) - 90.0           # 转为相对水平的偏角
        if -_MAX_DESKEW_ANGLE <= deg <= _MAX_DESKEW_ANGLE:
            angles.append(deg)
    if not angles:
        return 0.0
    return float(np.median(angles))


def _rotate(img: np.ndarray, angle: float) -> np.ndarray:
    """绕中心旋转 angle 度，边角用白色填充"""
    h, w = img.shape[:2]
    matrix = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
    return cv2.warpAffine(
        img, matrix, (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255),
    )


def _upscale_if_small(img: np.ndarray) -> np.ndarray:
    """短边过小时等比放大到目标尺寸"""
    h, w = img.shape[:2]
    short_edge = min(h, w)
    min_short_edge = max(1, settings.ocr_preprocess_min_short_edge)
    target_short_edge = max(min_short_edge, settings.ocr_preprocess_target_short_edge)
    if short_edge >= min_short_edge:
        return img
    scale = target_short_edge / short_edge
    return cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)


def _enhance_contrast(img: np.ndarray) -> np.ndarray:
    """对亮度通道做 CLAHE 自适应对比度增强（轻度）"""
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l_chan, a_chan, b_chan = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l_chan = clahe.apply(l_chan)
    return cv2.cvtColor(cv2.merge((l_chan, a_chan, b_chan)), cv2.COLOR_LAB2BGR)


def preprocess_image(image_bytes: bytes) -> bytes:
    """
    OCR 识别前的图像预处理入口。
    任何异常均记录日志并返回原始字节，保证主流程不中断。
    """
    try:
        img = _load_as_bgr(image_bytes)

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        angle = _detect_skew_angle(gray)
        if abs(angle) > 0.3:                      # 偏角足够明显才旋转
            img = _rotate(img, angle)

        img = _upscale_if_small(img)
        img = _enhance_contrast(img)

        jpeg_quality = max(60, min(95, settings.ocr_preprocess_jpeg_quality))
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
        if not ok:
            logger.warning("预处理图编码失败，回退原图")
            return image_bytes
        return buf.tobytes()
    except Exception as e:
        logger.warning("图像预处理异常，回退原图：%s", e)
        return image_bytes
