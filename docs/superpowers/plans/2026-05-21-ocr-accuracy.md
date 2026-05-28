# OCR 识别精度优化 Implementation Plan（修订版）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用阿里云百炼 `qwen-vl-ocr-latest` 替换 OCR 引擎，叠加图像预处理与「模型抽取 + 正则兜底」双路结构化提取，提升药盒识别精度，并提供可量化评测脚本。

**Architecture:** 新增 `app/ocr/pipeline.py` 编排「预处理 → qwen-vl-ocr → 正则兜底 → 双路合并」。`qwen_ocr_client.py` 一次调用产出 `raw_text` 与模型字段；`text_parser` 精简为正则兜底；`ocr_service` 只管存库。完全移除阿里云 `RecognizeGeneral`。

**Tech Stack:** Python 3.12、FastAPI、SQLAlchemy 异步、阿里云百炼 qwen-vl-ocr（DashScope OpenAI 兼容接口）、Pillow + opencv-python-headless、httpx、pytest + pytest-asyncio。

**设计文档：** `docs/superpowers/specs/2026-05-21-ocr-accuracy-design.md`

---

## 执行环境约定

- 全部命令在 `backend/` 目录下执行，且已激活 Python 虚拟环境。
- 测试框架 `pytest`；Task 1 创建 `backend/pytest.ini`（`asyncio_mode = auto`），之后 `async def test_*` 无需手动加 marker。
- 分支已建好 `feat/ocr-accuracy`。提交信息用中文，不加 `Co-Authored-By` 等署名 trailer。

---

## Task 1: 配置、依赖与测试基建

**Files:**
- Create: `backend/pytest.ini`
- Modify: `backend/app/config.py`
- Modify: `backend/requirements.txt`
- Modify: `backend/Dockerfile`
- Modify: `backend/.env.example`
- Modify: `.env.example`
- Modify: `.gitignore`
- Test: `backend/tests/test_config.py`

- [ ] **Step 1: 创建 pytest 配置**

Create `backend/pytest.ini`：

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
```

- [ ] **Step 2: 写失败测试**

Create `backend/tests/test_config.py`：

```python
from app.config import Settings


def test_ocr_settings_have_defaults(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "x" * 40)
    s = Settings()
    assert s.dashscope_api_key == ""
    assert s.qwen_ocr_model == "qwen-vl-ocr-latest"


def test_old_aliyun_ocr_settings_removed():
    # 直接查类的字段注册表，语义无歧义、无需实例化
    assert "aliyun_ocr_access_key_id" not in Settings.model_fields
    assert "deepseek_api_key" not in Settings.model_fields
```

- [ ] **Step 3: 运行测试确认失败**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL，`AttributeError: 'Settings' object has no attribute 'dashscope_api_key'`

- [ ] **Step 4: 替换 OCR 配置项**

Modify `backend/app/config.py`，将这段：

```python
    # DeepSeek API 配置
    deepseek_api_key: str = ""

    # 阿里云 OCR API 配置
    aliyun_ocr_access_key_id: str = ""
    aliyun_ocr_access_key_secret: str = ""
```

替换为：

```python
    # 阿里云百炼 qwen-vl-ocr OCR 配置
    dashscope_api_key: str = ""
    qwen_ocr_model: str = "qwen-vl-ocr-latest"
```

- [ ] **Step 4b: 为 Settings 增加 `extra="ignore"`**

`pydantic-settings` 默认对 `.env` 文件中未声明的多余键抛 `ValidationError`。移除阿里云 OCR 字段后，真实 `.env`（含旧 `ALIYUN_OCR_*` 等残留键）会导致 `Settings` 初始化失败、测试在 collection 阶段即崩溃。让 `Settings` 容忍多余键。

Modify `backend/app/config.py`，将：

```python
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
```

替换为：

```python
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",   # 容忍 .env 中未声明的多余键，避免旧配置残留导致启动失败
    )
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS（2 passed）

- [ ] **Step 6: 调整依赖**

Modify `backend/requirements.txt`，将这段：

```
# ===== 阿里云 OCR SDK =====
alibabacloud_ocr_api20210707>=3.1.3
alibabacloud-tea-openapi>=0.4.4
```

替换为：

```
# ===== 图像预处理（OCR 精度优化）=====
Pillow==11.0.0
opencv-python-headless==4.10.0.84
```

- [ ] **Step 7: 安装并验证新依赖**

Run: `pip install -r requirements.txt`
Expected: `Pillow` 与 `opencv-python-headless` 安装成功。

Run: `python -c "import cv2, PIL; print(cv2.__version__, PIL.__version__)"`
Expected: 打印两个版本号，无报错。

- [ ] **Step 8: Dockerfile 补充 opencv 运行时系统库**

Modify `backend/Dockerfile`，将这段（第 46-50 行附近）：

```dockerfile
# libmagic 预留给 WS3 文件头校验；tzdata 设置时区；gosu 供 entrypoint 降权
# 健康检查改用 Python stdlib，省去 curl 依赖 + 减小镜像体积
RUN sed -i "s|http://deb.debian.org/debian|${APT_MIRROR}|g; s|http://security.debian.org/debian-security|${APT_MIRROR}-security|g" /etc/apt/sources.list.d/debian.sources \
    && apt-get -o Acquire::Retries=5 -o Acquire::http::Timeout=120 update \
    && apt-get install -y --no-install-recommends libmagic1 tzdata gosu \
```

替换为：

```dockerfile
# libmagic 预留给 WS3 文件头校验；tzdata 设置时区；gosu 供 entrypoint 降权
# libglib2.0-0 供 opencv-python-headless 运行时链接
# 健康检查改用 Python stdlib，省去 curl 依赖 + 减小镜像体积
RUN sed -i "s|http://deb.debian.org/debian|${APT_MIRROR}|g; s|http://security.debian.org/debian-security|${APT_MIRROR}-security|g" /etc/apt/sources.list.d/debian.sources \
    && apt-get -o Acquire::Retries=5 -o Acquire::http::Timeout=120 update \
    && apt-get install -y --no-install-recommends libmagic1 tzdata gosu libglib2.0-0 \
```

- [ ] **Step 9: 更新 backend/.env.example**

Modify `backend/.env.example`，将这段：

```
# ===== 阿里云 OCR API 配置 =====
# 在阿里云控制台申请 RAM 子账号 AccessKey：
#   https://ram.console.aliyun.com/users
# 并为其授权 AliyunOCRFullAccess 或自定义最小权限策略。
ALIYUN_OCR_ACCESS_KEY_ID=your_access_key_id_here
ALIYUN_OCR_ACCESS_KEY_SECRET=your_access_key_secret_here

# ===== DeepSeek API（可选，用于后续 AI 辅助解析）=====
DEEPSEEK_API_KEY=
```

替换为：

```
# ===== 阿里云百炼 qwen-vl-ocr OCR 配置 =====
# 开通百炼后在控制台获取 API Key：https://bailian.console.aliyun.com/
DASHSCOPE_API_KEY=
QWEN_OCR_MODEL=qwen-vl-ocr-latest
```

- [ ] **Step 10: 更新根 .env.example**

Modify `.env.example`，将这段：

```
# ===== 阿里云 OCR =====
ALIYUN_OCR_ACCESS_KEY_ID=REPLACE_WITH_YOUR_ACCESS_KEY_ID
ALIYUN_OCR_ACCESS_KEY_SECRET=REPLACE_WITH_YOUR_ACCESS_KEY_SECRET
```

替换为：

```
# ===== 阿里云百炼 qwen-vl-ocr OCR =====
# 开通百炼后在控制台获取：https://bailian.console.aliyun.com/
DASHSCOPE_API_KEY=REPLACE_WITH_YOUR_DASHSCOPE_API_KEY
QWEN_OCR_MODEL=qwen-vl-ocr-latest
```

再将文件末尾这段整体删除：

```
# ===== DeepSeek（可选）=====
DEEPSEEK_API_KEY=
```

- [ ] **Step 11: 更新 .gitignore**

Modify `.gitignore`，将这段：

```
# 上传文件
backend/uploads/*
!backend/uploads/.gitkeep
```

替换为：

```
# 上传文件
backend/uploads/*
!backend/uploads/.gitkeep

# OCR 评测测试图（本地资产，不入库）
backend/tests/ocr_eval/images/*
!backend/tests/ocr_eval/images/.gitkeep
```

- [ ] **Step 12: 提交**

```bash
git add backend/pytest.ini backend/tests/test_config.py backend/app/config.py backend/requirements.txt backend/Dockerfile backend/.env.example .env.example .gitignore
git commit -m "chore: 调整 OCR 配置与依赖，切换至 qwen-vl-ocr

- config 移除阿里云 OCR / DeepSeek，新增 DashScope 配置
- requirements 移除阿里云 OCR SDK，引入 Pillow 与 opencv
- Dockerfile 补充 libglib2.0-0
- 新增 pytest.ini 启用 asyncio 自动模式"
```

---

## Task 2: 图像预处理模块

**Files:**
- Create: `backend/app/ocr/image_preprocess.py`
- Test: `backend/tests/test_image_preprocess.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_image_preprocess.py`：

```python
import cv2
import numpy as np

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


def test_preprocess_garbage_bytes_returns_original():
    garbage = b"this is not an image"
    assert preprocess_image(garbage) == garbage
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_image_preprocess.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.ocr.image_preprocess'`

- [ ] **Step 3: 实现预处理模块**

Create `backend/app/ocr/image_preprocess.py`：

```python
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

logger = logging.getLogger(__name__)

# 短边低于此像素值时等比放大
_MIN_SHORT_EDGE = 1000
# 放大后短边目标像素值
_TARGET_SHORT_EDGE = 1600
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
    if short_edge >= _MIN_SHORT_EDGE:
        return img
    scale = _TARGET_SHORT_EDGE / short_edge
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

        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 95])
        if not ok:
            logger.warning("预处理图编码失败，回退原图")
            return image_bytes
        return buf.tobytes()
    except Exception as e:
        logger.warning("图像预处理异常，回退原图：%s", e)
        return image_bytes
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_image_preprocess.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: 提交**

```bash
git add backend/app/ocr/image_preprocess.py backend/tests/test_image_preprocess.py
git commit -m "feat: 新增图像预处理模块

EXIF 方向修正 + 自动纠偏 + 分辨率放大 + 轻度对比度增强；
保留彩色不二值化，异常时安全回退原图。"
```

---

## Task 3: text_parser 精简为正则兜底

**Files:**
- Modify: `backend/app/ocr/text_parser.py`
- Test: `backend/tests/test_text_parser.py`

移除已无用的 Tier 3 DeepSeek 相关代码，`parse_drug_info` 仅保留 Tier 1 正则 + Tier 2 模糊匹配。

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_text_parser.py`：

```python
import app.ocr.text_parser as tp
from app.ocr.text_parser import parse_drug_info


def test_parse_extracts_core_fields_via_regex():
    raw = "\n".join([
        "阿莫西林胶囊",
        "批准文号：国药准字H20044416",
        "批号：20240315",
        "生产日期：2024-03-15",
        "有效期至：2026-03-01",
    ])
    result = parse_drug_info(raw)
    assert result.name == "阿莫西林胶囊"
    assert result.approval_number == "国药准字H20044416"
    assert result.batch_number == "20240315"
    assert result.production_date == "2024-03-15"
    assert result.expiry_date == "2026-03-01"


def test_parse_empty_text_returns_all_none():
    result = parse_drug_info("")
    assert result.name is None
    assert result.batch_number is None
    assert result.expiry_date is None


def test_deepseek_tier3_removed():
    # 精简后不应再保留任何 DeepSeek/LLM 兜底符号
    assert not hasattr(tp, "_extract_via_llm")
    assert not hasattr(tp, "_LLM_SYSTEM_PROMPT")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_text_parser.py -v`
Expected: FAIL，`test_deepseek_tier3_removed` 断言失败（`_extract_via_llm` 仍存在）。

- [ ] **Step 3: 精简导入**

Modify `backend/app/ocr/text_parser.py`，将文件顶部导入段：

```python
import re
import json
import os
import difflib
import logging
from typing import Optional

import httpx

from app.schemas.ocr import ExtractedDrugData
```

替换为：

```python
import re
import difflib
import logging
from typing import Optional

from app.schemas.ocr import ExtractedDrugData
```

- [ ] **Step 4: 更新模块文档字符串**

Modify `backend/app/ocr/text_parser.py`，将文件顶部文档字符串：

```python
"""
药品信息文本解析器 — 多级兜底策略 Pipeline

执行层级：
  Tier 1 — 增强型正则提取（中文关键词间加 \\s* 兼容排版空格）
  Tier 2 — difflib 模糊匹配兜底（正则失败时启动，相似度阈值 > 0.8）
  Tier 3 — DeepSeek LLM 兜底（核心字段均为空时触发，读取 DEEPSEEK_API_KEY）

对外接口保持不变：parse_drug_info(raw_text: str) -> ExtractedDrugData
"""
```

替换为：

```python
"""
药品信息文本解析器 — 正则兜底（Tier 1 + Tier 2）

执行层级：
  Tier 1 — 增强型正则提取（中文关键词间加 \\s* 兼容排版空格）
  Tier 2 — difflib 模糊匹配兜底（正则失败时启动，相似度阈值 > 0.8）

主接口：parse_drug_info(raw_text: str) -> ExtractedDrugData
本模块在 app.ocr.pipeline 中作为 qwen-vl-ocr 模型抽取的兜底安全网，
对模型未给出的字段在高质量 raw_text 上做正则补全。
"""
```

- [ ] **Step 5: 删除整个 Tier 3 区段**

用 Read 打开 `backend/app/ocr/text_parser.py`。删除一段连续代码：

- **起始行**（含）——下面这三行注释：
  ```python
  # ============================================================
  # Tier 3 — LLM 提取接口（当前为 Stub，未激活）
  # ============================================================
  ```
- **结束行**（含）——`_extract_via_llm` 函数的最后三行：
  ```python
      except Exception as e:
          logger.error("[Tier 3] DeepSeek 提取异常：%s", e)
      return None
  ```

这两处之间的全部内容（含 `_LLM_SYSTEM_PROMPT` 常量与 `_extract_via_llm` 整个函数，约 66 行）一并删除。删除后，下一段保留内容应为 `# 工具函数` 区段：

```python
# ============================================================
# 工具函数
# ============================================================
```

- [ ] **Step 6: 移除 parse_drug_info 内的 Tier 3 调用**

Modify `backend/app/ocr/text_parser.py`，将这段：

```python
    # ── Tier 3: LLM 兜底（批号、有效期、名称三个核心字段均为空时触发）─

    core_fields_empty = not batch_number and not expiry_date and not name
    if core_fields_empty:
        logger.info("[Tier 3] 核心字段均为空，尝试 LLM 提取")
        llm_result = _extract_via_llm(text)
        if llm_result:
            name          = name          or llm_result.get("name")
            approval      = approval      or llm_result.get("approval_number")
            manufacturer  = manufacturer  or llm_result.get("manufacturer")
            specification = specification or llm_result.get("specification")
            batch_number  = batch_number  or llm_result.get("batch_number")
            production_date = production_date or _normalize_date_str(
                llm_result.get("production_date") or ""
            )
            expiry_date = expiry_date or _normalize_date_str(
                llm_result.get("expiry_date") or ""
            )
            if quantity is None and llm_result.get("quantity") is not None:
                try:
                    quantity = int(llm_result["quantity"])
                except (ValueError, TypeError):
                    pass

    return ExtractedDrugData(
```

替换为：

```python
    return ExtractedDrugData(
```

- [ ] **Step 7: 运行测试确认通过**

Run: `python -m pytest tests/test_text_parser.py -v`
Expected: PASS（3 passed）

- [ ] **Step 8: 提交**

```bash
git add backend/app/ocr/text_parser.py backend/tests/test_text_parser.py
git commit -m "refactor: text_parser 精简为正则兜底

移除已无用的 Tier 3 DeepSeek 提取（_extract_via_llm、_LLM_SYSTEM_PROMPT
及 parse_drug_info 内的调用），parse_drug_info 仅保留正则与模糊匹配。"
```

---

## Task 4: qwen-vl-ocr 客户端

**Files:**
- Create: `backend/app/ocr/qwen_ocr_client.py`
- Test: `backend/tests/test_qwen_ocr_client.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_qwen_ocr_client.py`：

```python
from app.ocr import qwen_ocr_client


def test_build_payload_uses_signed_image_url_and_pixels(monkeypatch):
    monkeypatch.setattr(qwen_ocr_client.settings, "qwen_ocr_model", "qwen-vl-ocr-latest")
    image_url = "https://oss.example.test/ocr/qwen/image.jpg?Signature=test"
    payload = qwen_ocr_client._build_payload(image_url)
    assert payload["model"] == "qwen-vl-ocr-latest"
    content = payload["messages"][0]["content"]
    image_part = next(p for p in content if p["type"] == "image_url")
    assert image_part["image_url"]["url"] == image_url
    assert image_part["min_pixels"] == 3072
    assert image_part["max_pixels"] == 8388608


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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_qwen_ocr_client.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.ocr.qwen_ocr_client'`

- [ ] **Step 3: 实现 qwen-vl-ocr 客户端**

Create `backend/app/ocr/qwen_ocr_client.py`：

```python
"""
通义千问 OCR 客户端 — 阿里云百炼 qwen-vl-ocr-latest

走百炼 OpenAI 兼容接口，一次调用产出图像完整文本 raw_text 与模型抽取的结构化字段。
未配置 DASHSCOPE_API_KEY 或 API/网络异常时抛 RuntimeError 交由上层处理。
"""
import json
import logging
import re

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# 阿里云百炼 OpenAI 兼容端点
_BAILIAN_ENDPOINT = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

# qwen-vl-ocr 图像像素范围（清晰度与 token 消耗的权衡）
_MIN_PIXELS = 3072
_MAX_PIXELS = 8388608

# 需要模型抽取的结构化字段
_DRUG_FIELDS = (
    "name", "approval_number", "manufacturer", "specification",
    "batch_number", "production_date", "expiry_date", "quantity",
)

# 提示词：要求模型同时输出完整文本与结构化字段
_OCR_PROMPT = """请识别这张药品包装图片，完成两件事并只输出一个 JSON 对象：
1. raw_text：图片中识别到的全部文字（保留换行）。
2. 提取以下字段，无法确定的填 null，禁止编造：
   name（药品通用名称）、approval_number（批准文号，如 国药准字H20044416）、
   manufacturer（生产企业全称）、specification（规格，如 0.25g×24粒）、
   batch_number（批号）、production_date（生产日期 YYYY-MM-DD）、
   expiry_date（有效期至 YYYY-MM-DD）、quantity（数量，整数）。
输出格式：{"raw_text": "...", "name": null, "approval_number": null, "manufacturer": null, "specification": null, "batch_number": null, "production_date": null, "expiry_date": null, "quantity": null}
只输出 JSON，不要任何额外说明文字。"""


def _build_payload(image_url: str) -> dict:
    """构造百炼 chat/completions 请求体，图片使用 OSS 临时签名 URL"""
    return {
        "model": settings.qwen_ocr_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": image_url},
                        "min_pixels": _MIN_PIXELS,
                        "max_pixels": _MAX_PIXELS,
                    },
                    {"type": "text", "text": _OCR_PROMPT},
                ],
            },
        ],
        "temperature": 0.01,
    }


def _parse_response(resp_json: dict) -> dict:
    """
    从百炼响应取出模型输出，解析为 {"raw_text": str, "fields": dict}。
    JSON 解析失败时把整段输出当作 raw_text，fields 留空交由正则兜底。
    """
    try:
        content = resp_json["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        logger.error("[QwenOCR] 响应结构异常：%s", resp_json)
        return {"raw_text": "", "fields": {}}

    # 模型可能用 ```json ... ``` 代码块包裹
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", content, re.DOTALL)
    raw = fenced.group(1) if fenced else content
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        logger.warning("[QwenOCR] 输出非合法 JSON，整段作为 raw_text 交由正则兜底")
        return {"raw_text": content if isinstance(content, str) else "", "fields": {}}

    if not isinstance(parsed, dict):
        return {"raw_text": content if isinstance(content, str) else "", "fields": {}}

    raw_text = parsed.get("raw_text") or ""
    fields = {f: parsed.get(f) for f in _DRUG_FIELDS}
    return {"raw_text": str(raw_text), "fields": fields}


async def recognize_drug(image_bytes: bytes) -> dict:
    """
    调用 qwen-vl-ocr-latest 识别药盒图片。
    返回 {"raw_text": str, "fields": dict}。
    未配置 DASHSCOPE_API_KEY 或 API/网络异常 → RuntimeError。
    """
    if not settings.dashscope_api_key:
        raise RuntimeError("未配置 DASHSCOPE_API_KEY，无法调用 qwen-vl-ocr 进行真实 OCR 识别")

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                _BAILIAN_ENDPOINT,
                headers={
                    "Authorization": f"Bearer {settings.dashscope_api_key}",
                    "Content-Type": "application/json",
                },
                json=_build_payload(image_bytes),
            )
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise RuntimeError(
            f"qwen-vl-ocr 调用失败 [{e.response.status_code}]: {e.response.text}"
        ) from e
    except Exception as e:
        raise RuntimeError(f"qwen-vl-ocr 请求异常: {e}") from e

    return _parse_response(resp.json())
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_qwen_ocr_client.py -v`
Expected: PASS（6 passed）

- [ ] **Step 5: 提交**

```bash
git add backend/app/ocr/qwen_ocr_client.py backend/tests/test_qwen_ocr_client.py
git commit -m "feat: 新增 qwen-vl-ocr 客户端

走阿里云百炼 OpenAI 兼容接口，一次调用产出 raw_text 与结构化字段；
JSON 解析失败时整段回退为 raw_text，未配置 key 时走 mock。"
```

---

## Task 5: 识别流水线编排

**Files:**
- Create: `backend/app/ocr/pipeline.py`
- Test: `backend/tests/test_pipeline.py`

- [ ] **Step 1: 写失败测试（纯函数部分）**

Create `backend/tests/test_pipeline.py`：

```python
from app.ocr import pipeline
from app.ocr.pipeline import RecognitionResult, _completeness, _merge
from app.schemas.ocr import ExtractedDrugData


def test_merge_prefers_model_fields():
    model = {"name": "阿莫西林胶囊", "batch_number": "20240315"}
    regex = ExtractedDrugData(name="正则名称", batch_number="REGEXBATCH", expiry_date="2026-03-01")
    merged = _merge(model, regex)
    assert merged.name == "阿莫西林胶囊"          # 模型优先
    assert merged.batch_number == "20240315"
    assert merged.expiry_date == "2026-03-01"      # 模型空缺 → 用正则


def test_merge_fills_empty_model_fields_with_regex():
    model = {"name": None, "batch_number": ""}
    regex = ExtractedDrugData(name="正则名称", batch_number="REGEXBATCH")
    merged = _merge(model, regex)
    assert merged.name == "正则名称"
    assert merged.batch_number == "REGEXBATCH"


def test_merge_normalizes_model_dates():
    merged = _merge({"expiry_date": "2026年03月"}, ExtractedDrugData())
    assert merged.expiry_date == "2026-03-01"


def test_merge_skips_invalid_model_quantity():
    merged = _merge({"quantity": "abc"}, ExtractedDrugData(quantity=5))
    assert merged.quantity == 5


def test_completeness_ratio():
    extracted = ExtractedDrugData(
        name="药", batch_number="B", production_date="2024-03-15", expiry_date="2026-03-01",
    )
    assert _completeness(extracted) == 0.5     # 8 字段填 4 个


def test_completeness_empty():
    assert _completeness(ExtractedDrugData()) == 0.0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_pipeline.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.ocr.pipeline'`

- [ ] **Step 3: 实现 pipeline 模块**

Create `backend/app/ocr/pipeline.py`：

```python
"""
OCR 识别流水线编排

流程：图像预处理 → qwen-vl-ocr 识别 → 正则兜底解析 → 双路合并
合并策略：模型抽取字段为主，空缺字段用正则在 raw_text 上补全。
"""
import logging
from dataclasses import dataclass

from app.ocr.image_preprocess import preprocess_image
from app.ocr.qwen_ocr_client import recognize_drug
from app.ocr.text_parser import _normalize_date_str, parse_drug_info
from app.schemas.ocr import ExtractedDrugData

logger = logging.getLogger(__name__)

_ALL_FIELDS = (
    "name", "approval_number", "manufacturer", "specification",
    "batch_number", "production_date", "expiry_date", "quantity",
)


@dataclass
class RecognitionResult:
    """识别流水线输出"""
    raw_text: str
    extracted: ExtractedDrugData
    confidence: float          # 字段完整度 = 非空字段数 / 8，作为置信度代理


def _is_empty(value) -> bool:
    """字段是否为空（None 或纯空白字符串）"""
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def _coerce(field: str, value):
    """把模型字段值规整为 ExtractedDrugData 所需类型；无法规整返回 None"""
    if _is_empty(value):
        return None
    if field in ("production_date", "expiry_date"):
        return _normalize_date_str(str(value))
    if field == "quantity":
        try:
            return int(value)
        except (ValueError, TypeError):
            return None
    return str(value).strip()


def _merge(model_fields: dict, regex: ExtractedDrugData) -> ExtractedDrugData:
    """双路合并：模型抽取字段为主，空缺用正则兜底结果补全。"""
    data = {}
    for field in _ALL_FIELDS:
        model_value = _coerce(field, model_fields.get(field))
        data[field] = model_value if model_value is not None else getattr(regex, field)
    return ExtractedDrugData(**data)


def _completeness(extracted: ExtractedDrugData) -> float:
    """字段完整度：非空字段数 / 总字段数，作为置信度代理"""
    filled = sum(1 for f in _ALL_FIELDS if not _is_empty(getattr(extracted, f)))
    return round(filled / len(_ALL_FIELDS), 2)


async def recognize_and_extract(image_bytes: bytes) -> RecognitionResult:
    """识别流水线主入口，供 ocr_service 调用。"""
    processed = preprocess_image(image_bytes)

    ocr = await recognize_drug(processed)
    raw_text = ocr.get("raw_text", "")
    model_fields = ocr.get("fields", {})

    # 正则兜底：在 qwen-vl-ocr 的高质量文本上解析
    regex_extracted = parse_drug_info(raw_text)

    merged = _merge(model_fields, regex_extracted)
    logger.info("[Pipeline] 识别完成，字段完整度 %.2f", _completeness(merged))

    return RecognitionResult(
        raw_text=raw_text,
        extracted=merged,
        confidence=_completeness(merged),
    )
```

- [ ] **Step 4: 运行测试确认纯函数测试通过**

Run: `python -m pytest tests/test_pipeline.py -v`
Expected: PASS（6 passed）

- [ ] **Step 5: 追加流水线编排测试**

在 `backend/tests/test_pipeline.py` 文件**末尾追加**：

```python
async def test_recognize_and_extract_merges_model_and_regex(monkeypatch):
    monkeypatch.setattr(pipeline, "preprocess_image", lambda b: b)

    async def fake_ocr(_):
        return {
            "raw_text": "阿莫西林胶囊\n批号：20240315\n有效期至：2026-03-01",
            "fields": {"name": "阿莫西林胶囊"},   # 模型只给出名称
        }

    monkeypatch.setattr(pipeline, "recognize_drug", fake_ocr)

    result = await pipeline.recognize_and_extract(b"image")
    assert result.extracted.name == "阿莫西林胶囊"        # 来自模型
    assert result.extracted.batch_number == "20240315"     # 模型空缺 → 正则补
    assert result.extracted.expiry_date == "2026-03-01"
    assert result.raw_text.startswith("阿莫西林胶囊")


async def test_recognize_and_extract_relies_on_regex_when_no_model_fields(monkeypatch):
    monkeypatch.setattr(pipeline, "preprocess_image", lambda b: b)

    async def fake_ocr(_):
        # 模型未给结构化字段（JSON 解析失败的情形），只有 raw_text
        return {
            "raw_text": "阿莫西林胶囊\n批号：20240315\n生产日期：2024-03-15\n有效期至：2026-03-01",
            "fields": {},
        }

    monkeypatch.setattr(pipeline, "recognize_drug", fake_ocr)

    result = await pipeline.recognize_and_extract(b"image")
    assert result.extracted.name == "阿莫西林胶囊"
    assert result.extracted.batch_number == "20240315"
    assert result.extracted.production_date == "2024-03-15"
    assert result.confidence > 0
```

- [ ] **Step 6: 运行全部 pipeline 测试确认通过**

Run: `python -m pytest tests/test_pipeline.py -v`
Expected: PASS（8 passed）

- [ ] **Step 7: 提交**

```bash
git add backend/app/ocr/pipeline.py backend/tests/test_pipeline.py
git commit -m "feat: 新增 OCR 识别流水线编排

统管预处理 → qwen-vl-ocr → 正则兜底 → 双路合并；
模型字段为主、空缺用正则补全，字段完整度作为置信度代理。"
```

---

## Task 6: ocr_service 接入流水线并删除旧客户端

**Files:**
- Modify: `backend/app/services/ocr_service.py`
- Delete: `backend/app/ocr/alibaba_client.py`
- Test: `backend/tests/test_ocr_service.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_ocr_service.py`：

```python
import pytest
from unittest.mock import AsyncMock

from app.core.exceptions import BusinessError
from app.models.ocr_record import OcrStatus
from app.ocr.pipeline import RecognitionResult
from app.schemas.ocr import ExtractedDrugData
from app.services import ocr_service


class _FakeSession:
    """最小异步 DB 会话替身：仅支持 add/flush/refresh"""
    def __init__(self):
        self.added = []

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        pass

    async def refresh(self, obj):
        pass


async def test_upload_and_recognize_writes_pipeline_result(monkeypatch, tmp_path):
    monkeypatch.setattr(ocr_service.settings, "upload_dir", str(tmp_path))

    fake_result = RecognitionResult(
        raw_text="阿莫西林胶囊",
        extracted=ExtractedDrugData(name="阿莫西林胶囊", batch_number="20240315"),
        confidence=0.25,
    )
    monkeypatch.setattr(ocr_service, "recognize_and_extract", AsyncMock(return_value=fake_result))

    record = await ocr_service.upload_and_recognize(
        db=_FakeSession(),
        image_bytes=b"fake-image-bytes",
        filename="test.jpg",
        content_type="image/jpeg",
        operator_id=1,
    )

    assert record.status == OcrStatus.success
    assert record.raw_text == "阿莫西林胶囊"
    assert record.confidence == 0.25
    assert record.extracted_data["name"] == "阿莫西林胶囊"
    assert record.extracted_data["confidence_estimated"] is True


async def test_upload_and_recognize_rejects_bad_content_type(monkeypatch, tmp_path):
    monkeypatch.setattr(ocr_service.settings, "upload_dir", str(tmp_path))
    with pytest.raises(BusinessError):
        await ocr_service.upload_and_recognize(
            db=_FakeSession(),
            image_bytes=b"x",
            filename="test.txt",
            content_type="text/plain",
            operator_id=1,
        )
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_ocr_service.py -v`
Expected: FAIL，`AttributeError: module 'app.services.ocr_service' has no attribute 'recognize_and_extract'`

- [ ] **Step 3: 替换 ocr_service 的导入**

Modify `backend/app/services/ocr_service.py`，将这两行：

```python
from app.ocr.alibaba_client import recognize_image
from app.ocr.text_parser import parse_drug_info
```

替换为：

```python
from app.ocr.pipeline import recognize_and_extract
```

- [ ] **Step 4: 改用流水线**

Modify `backend/app/services/ocr_service.py`，将这段：

```python
    # 5. 调用 OCR（网络失败不抛出，而是将错误写入记录）
    try:
        ocr_result = await recognize_image(image_bytes)
        raw_text = ocr_result.get("raw_text", "")
        confidence = ocr_result.get("confidence", 0.0)
        confidence_estimated = ocr_result.get("confidence_estimated", False)

        # 6. 解析结构化药品信息
        extracted = parse_drug_info(raw_text)

        extracted_dict = extracted.model_dump(exclude_none=True)
        extracted_dict["confidence_estimated"] = confidence_estimated  # 记录置信度来源

        record.raw_text = raw_text
        record.extracted_data = extracted_dict
        record.confidence = confidence
        record.status = OcrStatus.success

    except Exception as e:
        logger.error("OCR 识别失败 record_id=%s: %s", record.id, e)
        record.status = OcrStatus.failed
        record.error_message = str(e)[:500]
```

替换为：

```python
    # 5. 调用识别流水线（预处理 → qwen-vl-ocr → 正则兜底；失败不抛出，写入记录）
    try:
        result = await recognize_and_extract(image_bytes)

        extracted_dict = result.extracted.model_dump(exclude_none=True)
        extracted_dict["confidence_estimated"] = True   # confidence 为字段完整度代理值

        record.raw_text = result.raw_text
        record.extracted_data = extracted_dict
        record.confidence = result.confidence
        record.status = OcrStatus.success

    except Exception as e:
        logger.error("OCR 识别失败 record_id=%s: %s", record.id, e)
        record.status = OcrStatus.failed
        record.error_message = str(e)[:500]
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m pytest tests/test_ocr_service.py -v`
Expected: PASS（2 passed）

- [ ] **Step 6: 删除旧的阿里云 OCR 客户端**

先确认无残留引用：
Run: `python -m pytest tests/ -q`
Expected: 全部 PASS（此时阿里云客户端已无人引用）。

再删除文件：

```bash
git rm backend/app/ocr/alibaba_client.py
```

确认无其它引用：
Run: `git grep -n "alibaba_client" -- backend/app`
Expected: 无输出（无残留引用）。

- [ ] **Step 7: 提交**

```bash
git add backend/app/services/ocr_service.py backend/tests/test_ocr_service.py
git commit -m "feat: ocr_service 接入识别流水线并移除阿里云 OCR 客户端

upload_and_recognize 改调 pipeline.recognize_and_extract；
删除 alibaba_client.py（RecognizeGeneral 已被 qwen-vl-ocr 取代）。"
```

---

## Task 7: OCR 评测脚本

**Files:**
- Create: `backend/scripts/__init__.py`
- Create: `backend/scripts/eval_ocr.py`
- Create: `backend/tests/ocr_eval/ground_truth.example.json`
- Create: `backend/tests/ocr_eval/images/.gitkeep`
- Test: `backend/tests/test_eval_ocr.py`

- [ ] **Step 1: 创建评测目录占位文件**

Create `backend/tests/ocr_eval/images/.gitkeep`（空文件）。

Create `backend/tests/ocr_eval/ground_truth.example.json`：

```json
{
  "示例-阿莫西林.jpg": {
    "name": "阿莫西林胶囊",
    "approval_number": "国药准字H20044416",
    "manufacturer": "广州白云山制药股份有限公司",
    "specification": "0.25g×24粒",
    "batch_number": "20240315",
    "production_date": "2024-03-15",
    "expiry_date": "2026-03-01",
    "quantity": 1
  }
}
```

- [ ] **Step 2: 创建 scripts 包标识**

Create `backend/scripts/__init__.py`（空文件，使 scripts 可被测试 import）。

- [ ] **Step 3: 写失败测试**

Create `backend/tests/test_eval_ocr.py`：

```python
from scripts.eval_ocr import _aggregate, _norm, _score_field


def test_norm_handles_none_and_whitespace():
    assert _norm(None) == ""
    assert _norm("  20240315 ") == "20240315"
    assert _norm(12) == "12"


def test_score_field_matches_after_normalization():
    assert _score_field("20240315", " 20240315 ") is True
    assert _score_field(1, "1") is True
    assert _score_field("A", "B") is False


def test_aggregate_computes_field_and_overall_accuracy():
    per_image = [
        {
            "filename": "a.jpg",
            "expected": {"name": "药A", "batch_number": "B1"},
            "fields": {"name": True, "batch_number": False},
        },
        {
            "filename": "b.jpg",
            "expected": {"name": "药B", "batch_number": "B2"},
            "fields": {"name": True, "batch_number": True},
        },
    ]
    report = _aggregate(per_image)
    assert report["name"]["hits"] == 2
    assert report["name"]["total"] == 2
    assert report["name"]["accuracy"] == 1.0
    assert report["batch_number"]["hits"] == 1
    assert report["batch_number"]["accuracy"] == 0.5
    assert report["_overall"]["hits"] == 3
    assert report["_overall"]["total"] == 4
    assert report["_overall"]["accuracy"] == 0.75
```

- [ ] **Step 4: 运行测试确认失败**

Run: `python -m pytest tests/test_eval_ocr.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'scripts.eval_ocr'`

- [ ] **Step 5: 实现评测脚本**

Create `backend/scripts/eval_ocr.py`：

```python
"""
OCR 识别精度评测脚本（本地手动运行）

用法：
  1. 把药盒图放入 backend/tests/ocr_eval/images/
  2. 参照 ground_truth.example.json 创建 ground_truth.json，
     键为图片文件名，值为人工标注的正确字段。
  3. 在 backend/ 目录下运行：python scripts/eval_ocr.py

脚本对每张图跑完整识别流水线，逐字段与标注比对，输出准确率。
会真实调用 qwen-vl-ocr 产生少量费用；不进 CI。
"""
import asyncio
import json
import sys
from pathlib import Path

# 确保能 import app 包
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ocr.pipeline import recognize_and_extract  # noqa: E402

_EVAL_DIR = Path(__file__).resolve().parent.parent / "tests" / "ocr_eval"
_IMAGES_DIR = _EVAL_DIR / "images"
_GROUND_TRUTH = _EVAL_DIR / "ground_truth.json"

_FIELDS = (
    "name", "approval_number", "manufacturer", "specification",
    "batch_number", "production_date", "expiry_date", "quantity",
)


def _norm(value) -> str:
    """归一化字段值用于比对：转字符串、去首尾空白"""
    if value is None:
        return ""
    return str(value).strip()


def _score_field(predicted, expected) -> bool:
    """单字段是否命中（归一化后完全相等）"""
    return _norm(predicted) == _norm(expected)


def _aggregate(per_image: list[dict]) -> dict:
    """汇总逐图结果，算每字段与总体准确率"""
    field_hits = {f: 0 for f in _FIELDS}
    field_total = {f: 0 for f in _FIELDS}
    for row in per_image:
        for f in _FIELDS:
            if f not in row["expected"]:
                continue
            field_total[f] += 1
            if row["fields"].get(f):
                field_hits[f] += 1

    report: dict = {}
    for f in _FIELDS:
        total = field_total[f]
        report[f] = {
            "hits": field_hits[f],
            "total": total,
            "accuracy": round(field_hits[f] / total, 3) if total else None,
        }
    all_hits = sum(field_hits.values())
    all_total = sum(field_total.values())
    report["_overall"] = {
        "hits": all_hits,
        "total": all_total,
        "accuracy": round(all_hits / all_total, 3) if all_total else None,
    }
    return report


async def _evaluate() -> int:
    if not _GROUND_TRUTH.exists():
        print(f"未找到标注文件：{_GROUND_TRUTH}")
        print("请参照 ground_truth.example.json 创建 ground_truth.json")
        return 1

    ground_truth = json.loads(_GROUND_TRUTH.read_text(encoding="utf-8"))
    if not ground_truth:
        print("标注文件为空，无可评测样本")
        return 1

    per_image: list[dict] = []
    for filename, expected in ground_truth.items():
        image_path = _IMAGES_DIR / filename
        if not image_path.exists():
            print(f"[跳过] 图片不存在：{filename}")
            continue
        result = await recognize_and_extract(image_path.read_bytes())
        predicted = result.extracted.model_dump()
        fields = {f: _score_field(predicted.get(f), expected.get(f)) for f in expected}
        per_image.append({"filename": filename, "expected": expected, "fields": fields})
        hit = sum(1 for v in fields.values() if v)
        print(f"[{filename}] 命中 {hit}/{len(fields)}  完整度={result.confidence}")

    if not per_image:
        print("没有可评测的图片（检查 images/ 目录与标注文件名是否一致）")
        return 1

    report = _aggregate(per_image)
    print("\n===== 逐字段准确率 =====")
    for f in _FIELDS:
        r = report[f]
        if r["total"]:
            print(f"  {f:<18} {r['hits']}/{r['total']}  准确率 {r['accuracy']}")
    overall = report["_overall"]
    print(f"\n总体准确率：{overall['hits']}/{overall['total']} = {overall['accuracy']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_evaluate()))
```

- [ ] **Step 6: 运行测试确认通过**

Run: `python -m pytest tests/test_eval_ocr.py -v`
Expected: PASS（3 passed）

- [ ] **Step 7: 运行完整测试套件**

Run: `python -m pytest tests/ -v`
Expected: 全部 PASS（27 项）。

- [ ] **Step 8: 提交**

```bash
git add backend/scripts/__init__.py backend/scripts/eval_ocr.py backend/tests/ocr_eval/ground_truth.example.json backend/tests/ocr_eval/images/.gitkeep backend/tests/test_eval_ocr.py
git commit -m "feat: 新增 OCR 识别精度评测脚本

对标注图集跑完整流水线，输出逐字段与总体准确率；
本地手动运行，不进 CI。"
```

---

## Task 8: 文档同步

**Files:**
- Modify: `README.md`
- Modify: `docs/DOCKER.md`

- [ ] **Step 1: 更新 README 项目简介**

Modify `README.md`，将这行：

```
> 通过阿里云 OCR 技术自动识别药品包装图片，提取药品名称、规格、批号、有效期等关键信息，并提供完整的药品档案管理、库存管理、批次追踪、过期预警及用户权限管理功能的智能化药品管理平台。
```

替换为：

```
> 通过 Qwen-OCR 视觉文字识别模型自动识别药品包装图片，提取药品名称、规格、批号、有效期等关键信息，并提供完整的药品档案管理、库存管理、批次追踪、过期预警及用户权限管理功能的智能化药品管理平台。
```

- [ ] **Step 2: 更新 README 功能特性**

Modify `README.md`，将这行：

```
- **OCR 智能识别** — 调用阿里云文字识别 API（RecognizeGeneral），正则引擎自动提取结构化字段
```

替换为：

```
- **OCR 智能识别** — 调用通义千问 Qwen-OCR 模型（qwen-vl-ocr-latest），模型抽取与正则兜底双路提取结构化字段
```

- [ ] **Step 3: 更新 README 技术栈表**

Modify `README.md`，将这行：

```
| OCR | 阿里云文字识别 API（alibabacloud_ocr_api20210707） |
```

替换为：

```
| OCR | 通义千问 Qwen-OCR（qwen-vl-ocr-latest，阿里云百炼） |
```

- [ ] **Step 4: 更新 README 环境变量表**

Modify `README.md`，将这两行：

```
| `ALIYUN_OCR_ACCESS_KEY_ID` | 阿里云 RAM AccessKey ID | ✅ |
| `ALIYUN_OCR_ACCESS_KEY_SECRET` | 阿里云 RAM AccessKey Secret | ✅ |
```

替换为：

```
| `DASHSCOPE_API_KEY` | 阿里云百炼 API Key（qwen-vl-ocr） | ✅ |
```

- [ ] **Step 5: 更新 README OCR 入库流程描述**

Modify `README.md`，将这行：

```
        ├─ 调用阿里云 OCR（线程池中执行，不阻塞事件循环）
```

替换为：

```
        ├─ 图像预处理 + 调用 qwen-vl-ocr 识别（异步 httpx）
```

- [ ] **Step 6: 更新 README 目录结构说明**

Modify `README.md`，将这行：

```
│   │   ├── ocr/            # OCR 识别引擎（阿里云客户端 + 文本解析器）
```

替换为：

```
│   │   ├── ocr/            # OCR 识别引擎（图像预处理 + Qwen-OCR 客户端 + 流水线 + 文本解析）
```

- [ ] **Step 7: 更新 DOCKER.md 环境变量表**

Modify `docs/DOCKER.md`，将这行：

```
| `ALIYUN_OCR_ACCESS_KEY_ID` / `ALIYUN_OCR_ACCESS_KEY_SECRET` | 阿里云 RAM 子账号 |
```

替换为：

```
| `DASHSCOPE_API_KEY` | 阿里云百炼 API Key（qwen-vl-ocr） |
```

- [ ] **Step 8: 提交**

```bash
git add README.md docs/DOCKER.md
git commit -m "docs: README 与 DOCKER 文档同步 qwen-vl-ocr 改动"
```

---

## 完成后

- 全部任务完成后，代码停在分支 `feat/ocr-accuracy`，处于「待合并」状态。
- 向用户汇报：完成事项、是否创建 PR、采用 squash / rebase / merge commit、是否保留分支。**未经用户确认不得合并到 main。**
- 真实链路验证（需用户在 `.env` 配置 `DASHSCOPE_API_KEY` 后自行执行）：
  1. 把 15~20 张真实药盒图放入 `backend/tests/ocr_eval/images/`，建好 `ground_truth.json`。
  2. 在 `backend/` 下运行 `python scripts/eval_ocr.py`，查看逐字段与总体准确率。

---

## 自查记录

- **规格覆盖**：设计文档第 5 节各模块——5.1 预处理 → Task 2；5.2 qwen_ocr_client → Task 4；5.3 pipeline → Task 5；5.4 text_parser 精简 → Task 3；5.5 ocr_service → Task 6；5.6 config → Task 1。第 6 节文件清单的新增/修改/删除均有对应任务（含删除 `alibaba_client.py` → Task 6、文档同步 → Task 8）。第 7 节评测脚本 → Task 7。第 9 节测试策略由各 Task 单测落地。
- **占位符扫描**：无 TBD / TODO；每个代码步骤均含完整代码或精确的删除边界。
- **类型一致性**：`RecognitionResult`、`recognize_and_extract`、`recognize_drug`、`preprocess_image`、`parse_drug_info`、`_merge`、`_completeness`、`_parse_response`、`_build_payload` 在定义任务与引用任务中命名一致；`recognize_drug` 返回的 `{"raw_text", "fields"}` 结构在 Task 4 定义、Task 5 消费一致。
