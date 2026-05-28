# OCR 识别精度优化 — 设计方案（修订版）

- 日期：2026-05-21
- 分支：`feat/ocr-accuracy`
- 范围：用 `qwen-vl-ocr-latest` 替换 OCR 引擎；图像预处理；双路结构化字段提取；配套评测脚本

## 0. 修订说明

初版设计为「阿里云高精版 OCR 为主 + 通义千问 VL 兜底」。在确认本项目为**毕业设计**、论文需把识别环节表述为"基于 OCR 模型"后，方案调整为：

- 以阿里云百炼的 **`qwen-vl-ocr-latest`**（官方定位为"通义千问 OCR 模型"）作为唯一 OCR 引擎。
- 完全移除原有的阿里云 `RecognizeGeneral`（`alibaba_client.py` 与 `ALIYUN_OCR_*` 配置）。
- 结构化字段提取改为双路：**模型抽取为主，正则为兜底安全网**。

## 1. 背景与目标

- 本项目是毕业设计。OCR 选型硬约束：方案要能在论文中表述为"基于 OCR 模型"。
- 当前链路 `RecognizeGeneral`（通用文字识别）+ 正则解析，对药盒这种版面复杂、字体多、字段分散的图像识别效果差。
- 目标：在不改动前端与上传/确认入库流程的前提下，替换后端 OCR 客户端，显著提升识别与字段提取精度，并提供可量化的评测手段。

## 2. 现状链路

```
前端上传 → POST /api/v1/ocr/upload → ocr.py → ocr_service.upload_and_recognize
  → alibaba_client.recognize_image()   调阿里云 RecognizeGeneral
  → text_parser.parse_drug_info()      正则 + difflib 模糊匹配解析字段
  → 存入 ocr_records
```

已知问题：

- `RecognizeGeneral` 是通用文字识别，对药盒复杂版面识别质量有限，错字漏字传导到下游。
- `text_parser` 的正则跑在质量不佳的 OCR 文本上，字段命中率低。
- 现有 Tier 3 DeepSeek 文本兜底触发条件为三个核心字段全空，几乎不生效。

## 3. 方案核心

**单一 OCR 引擎 + 双路结构化提取。**

`qwen-vl-ocr-latest` 一次调用，同时产出：

1. `raw_text` —— 图像的完整识别文本（qwen-vl-ocr 的核心强项，文本质量远高于 `RecognizeGeneral`）。
2. 模型抽取的结构化字段 JSON（药品名称、批准文号等）。

> **必须正视的技术点**：`qwen-vl-ocr` 是 OCR 专精模型，强于"读字"，但对"严格按 schema 输出 JSON"的指令遵循不如通用视觉模型稳定，偶尔会输出多余说明文字或不规范 JSON、漏字段。
>
> 因此**不只依赖模型 JSON**。`text_parser` 的正则保留为兜底安全网——qwen-vl-ocr 产出的 `raw_text` 质量极高，正则跑在干净文本上非常可靠。模型 JSON 缺哪个字段，就用正则在 `raw_text` 上补哪个。正则由"主力"降级为"安全网"，与"不再完全依赖正则"的诉求一致。

论文表述：**"系统基于 Qwen-OCR 视觉文字识别模型完成药品包装图像识别，并采用规则化提取与模型化抽取双路结构化策略实现药品信息入库。"**

## 4. 目标架构

```
图片字节
  │
  ├─[方案1] 图像预处理   image_preprocess.py   EXIF修正 / 纠偏 / 放大 / 轻度增强
  │
  ├─       OCR 识别      qwen_ocr_client.py    调 qwen-vl-ocr-latest（百炼 OpenAI 兼容接口）
  │         → raw_text + 模型抽取的字段 JSON
  │
  └─       双路合并      pipeline.py
            ├ text_parser.parse_drug_info(raw_text)  正则解析（兜底）
            └ 合并：模型字段为主，空缺用正则补
                → RecognitionResult → ocr_service 存库
```

前端、`/api/v1/ocr/upload` 上传接口、确认入库流程均不改动。

## 5. 各模块设计

### 5.1 图像预处理 `app/ocr/image_preprocess.py`（新增，方案1）

`preprocess_image(image_bytes: bytes) -> bytes`，依次执行：

1. EXIF 方向修正——Pillow `ImageOps.exif_transpose`。
2. 自动纠偏 deskew——opencv 霍夫变换检测倾斜角并旋转校正。
3. 分辨率检查——短边过低时等比放大。
4. 轻度对比度增强（CLAHE）。

保留彩色、不二值化。任何异常安全返回原始字节。预处理对 qwen-vl-ocr 同样有益（清晰、摆正的图识别更准）。

依赖：新增 `Pillow`、`opencv-python-headless`。

### 5.2 OCR 客户端 `app/ocr/qwen_ocr_client.py`（新增）

`async def recognize_drug(image_bytes: bytes) -> dict`，返回 `{"raw_text": str, "fields": dict}`。

- 走阿里云百炼 OpenAI 兼容接口：`https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions`。
- 模型 `settings.qwen_ocr_model`（默认 `qwen-vl-ocr-latest`）。
- 请求体：单条 user 消息，`content` 含图片项（OSS 临时签名 URL，附 `min_pixels` / `max_pixels`）与文本项（提示词要求输出含 `raw_text` 及 8 个字段的 JSON）。提示词写在 user 文本里，不用 system 消息（qwen-vl-ocr 对 system 角色支持弱）。
- 响应解析：取模型输出，剥离 ` ```json ` 代码块后 `json.loads`。
  - 解析成功且为 dict：`raw_text` 取 `raw_text` 键，`fields` 取其余 8 个字段键。
  - 解析失败：把模型整段输出当作 `raw_text`，`fields` 为空 dict（交由正则兜底）。
- 复用 `httpx` 调百炼，使用 `oss2` 生成 OSS 临时签名 URL。
- 未配置 `DASHSCOPE_API_KEY` 或 API 错误时抛 `RuntimeError`，由 `ocr_service` 捕获写入失败记录；系统不返回假识别结果。

### 5.3 识别流水线 `app/ocr/pipeline.py`（新增）

```python
@dataclass
class RecognitionResult:
    raw_text: str
    extracted: ExtractedDrugData
    confidence: float          # 字段完整度 = 非空字段数 / 8，作为置信度代理
```

`async def recognize_and_extract(image_bytes) -> RecognitionResult`：

1. `preprocess_image` 预处理。
2. `qwen_ocr_client.recognize_drug` 取 `raw_text` 与模型 `fields`。
3. `text_parser.parse_drug_info(raw_text)` 正则解析。
4. `_merge`：逐字段，模型值非空则用模型值，否则用正则值；日期、数量做类型规整与归一化。
5. `confidence` = 合并后非空字段数 / 8。

qwen-vl-ocr 无逐字符置信度，故 `confidence` 用"字段完整度"代理，并在 `extracted_data` 中标记 `confidence_estimated=True`。

### 5.4 文本解析 `app/ocr/text_parser.py`（精简）

- `parse_drug_info` 保留 Tier 1 正则 + Tier 2 difflib 模糊匹配，作为正则兜底。
- **移除** Tier 3 DeepSeek 相关：`_extract_via_llm`、`_LLM_SYSTEM_PROMPT`，以及 `parse_drug_info` 内的 Tier 3 调用块；清理随之失效的 `os` / `json` / `httpx` 导入。

### 5.5 业务服务 `app/services/ocr_service.py`（修改）

`upload_and_recognize` 改调 `pipeline.recognize_and_extract`，把 `raw_text` / `extracted_data` / `confidence` 写入 `OcrRecord`。其余（文件保存、`confirm_record` 入库）不变。

### 5.6 配置 `app/config.py`（修改）

- 移除：`aliyun_ocr_access_key_id`、`aliyun_ocr_access_key_secret`、`deepseek_api_key`。
- 新增：`dashscope_api_key: str = ""`、`qwen_ocr_model: str = "qwen-vl-ocr-latest"`。

## 6. 文件改动清单

### 新增

| 文件 | 职责 |
| --- | --- |
| `backend/app/ocr/image_preprocess.py` | 图像几何预处理 |
| `backend/app/ocr/qwen_ocr_client.py` | qwen-vl-ocr-latest 调用客户端 |
| `backend/app/ocr/pipeline.py` | 识别流水线编排：预处理 → OCR → 正则兜底 → 合并 |
| `backend/scripts/eval_ocr.py` | 本地评测脚本 |
| `backend/scripts/__init__.py` | 使 scripts 可被测试导入 |
| `backend/tests/ocr_eval/ground_truth.example.json` | 人工标注模板 |
| `backend/tests/ocr_eval/images/.gitkeep` | 测试图目录占位 |
| `backend/pytest.ini` | 启用 pytest asyncio 自动模式 |

### 修改

| 文件 | 改动 |
| --- | --- |
| `backend/app/ocr/text_parser.py` | 移除 Tier 3 DeepSeek，精简为正则兜底 |
| `backend/app/services/ocr_service.py` | `upload_and_recognize` 改调 `pipeline` |
| `backend/app/config.py` | 移除阿里云 OCR / DeepSeek 配置，新增 DashScope 配置 |
| `backend/requirements.txt` | 新增 `Pillow`、`opencv-python-headless`；移除阿里云 OCR SDK |
| `backend/Dockerfile` | runtime 阶段补 `libglib2.0-0`（opencv 运行依赖） |
| `.env.example`、`backend/.env.example` | OCR 相关配置项同步调整 |
| `docker-compose.yml` | 后端容器 OCR 相关环境变量同步调整 |
| 根 `.gitignore` | 忽略 `backend/tests/ocr_eval/images/*` |

### 删除

| 文件 | 原因 |
| --- | --- |
| `backend/app/ocr/alibaba_client.py` | 阿里云 RecognizeGeneral 已被 qwen-vl-ocr 取代 |

### 新增配置项

```
DASHSCOPE_API_KEY=                       # 阿里云百炼 API Key
QWEN_OCR_MODEL=qwen-vl-ocr-latest        # OCR 模型
```

## 7. 评测脚本

`backend/scripts/eval_ocr.py`：把药盒图放入 `backend/tests/ocr_eval/images/`，按 `ground_truth.example.json` 格式写好人工标注。脚本对每张图跑完整 `pipeline`，逐字段比对，输出每字段与总体准确率。本地手动运行，会真实调用 qwen-vl-ocr 产生少量费用（学生券可覆盖），不进 CI。建议标注 15~20 张、覆盖不同药盒版式。

## 8. 已知局限

- `qwen-vl-ocr` 对结构化 JSON 的指令遵循不如通用 VLM 稳定——正则兜底正是为此而设。
- 若模型把字段填错（非空但错误），双路合并以模型为主、不会被正则纠正；正则只补空缺。完整交叉校验不在本次范围。
- 评测脚本可信度取决于标注样本量与版式覆盖度。

## 9. 测试策略

- 新建 `backend/pytest.ini`（`asyncio_mode = auto`）。
- `image_preprocess`：验证输出可解码、小图被放大、异常输入回退原图。
- `qwen_ocr_client`：`_build_payload` / `_parse_response` 为纯函数，单测覆盖 OSS 临时签名 URL、JSON 解析、代码块剥离、解析失败回退；HTTP 调用 mock。
- `text_parser`：`parse_drug_info` 对纯文本的正则提取行为补单测，确保精简后无回归。
- `pipeline`：`_merge`、`confidence` 计算为纯逻辑，单测覆盖模型优先、空缺补正则、日期归一化、非法数量跳过；编排函数用 mock 覆盖。
- `ocr_service`：mock `recognize_and_extract` + 最小 DB 会话替身，验证记录字段写入。
- `eval_ocr`：`_score_field`、`_aggregate` 纯函数单测。

## 10. 交付方式

- 全部改动在分支 `feat/ocr-accuracy` 上提交，提交信息使用中文。
- 完成并自测后停在「待合并」状态，向用户汇报，确认合并方式后再并入 `main`。
- 真实链路验证需用户配置 `DASHSCOPE_API_KEY` 后，用评测脚本对真实药盒图跑分。
