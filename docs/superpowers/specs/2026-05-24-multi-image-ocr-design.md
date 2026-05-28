# 多图 OCR 药盒识别设计方案

- 日期：2026-05-24
- 范围：OCR 上传从单张图片升级为同一药盒多面照片；多图字段合并；跨图一致性校验；DeepSeek V4 Pro 辅助判断；前端人工审核提示
- 目标：允许药品包装信息分散在多个面时一次上传多张照片，最终合并成一条 OCR 待确认入库记录，同时尽量避免把不同药盒的信息误拼成同一条库存记录。

## 1. 背景与目标

当前系统的 OCR 链路只支持单张图片：

```
前端选择单个 file
  -> POST /api/v1/ocr/upload
  -> ocr_service.create_upload_record 保存 uploads/ocr/<uuid>.<ext>
  -> 后台调用 recognize_and_extract(image_bytes)
  -> ocr_records.image_path / raw_text / extracted_data / confidence
  -> 用户确认入库
```

真实药盒经常把药品名称、批准文号、生产企业、规格、批号、生产日期、有效期等信息分散在不同包装面。只拍一张图会导致字段缺失，影响入库效率。

本次设计将上传语义调整为：**一次上传只对应一种药品盒子的不同面，后端把多张照片整合成一条 OCR 记录。**

关键安全目标：

- 有明确字段冲突时，阻止错误合并。
- 无重叠字段时，使用 LLM 辅助分析，但前端必须提示人工审核。
- LLM 只作为辅助意见，不能覆盖规则冲突，也不能替代用户确认。

## 2. 非目标

- 不做多药品批量上传。一次上传仍只服务一个药盒。
- 不让 LLM 直接决定入库结果。入库仍由药师或管理员人工确认。
- 不要求第一版做图片视觉相似度模型。第一版只基于 OCR 文本和结构化字段校验。
- 不改变确认入库后创建 Drug、DrugBatch、InventoryRecord 的业务含义。

## 3. 推荐方案

采用“多图单记录”方案：

1. 前端允许选择 1 至 N 张图片，N 由配置限制，第一版建议默认最大 6 张。
2. 后端创建一条 `ocr_records` 主记录。
3. 每张图片保存为一条子记录，记录路径、顺序、单图 OCR 文本、单图结构化结果、单图状态。
4. 后台逐张 OCR。
5. 后端先进行规则一致性校验，再进行字段合并。
6. 当规则无法交叉验证时，调用 DeepSeek V4 Pro 做 OCR 文本级辅助判断。
7. 最终仍输出一条合并后的 OCR 记录，由前端展示所有图片、合并字段、每张图来源和一致性风险提示。

不采用“多选后创建多条 OCR 记录”的原因：它不能解决字段分散在不同面的问题，仍需要用户手动拼信息。

不采用“多张图片一次性传给 OCR 模型”的原因：当前项目的流水线、错误处理、历史记录和测试都围绕单图识别建立；逐张 OCR 更易保存证据、定位冲突、控制失败范围，也能复用现有 `recognize_and_extract`。

## 4. 数据模型设计

### 4.1 保留 `ocr_records`

`ocr_records` 继续作为一条 OCR 任务和入库确认的主记录。

保留 `image_path` 字段作为封面图路径，取第一张上传图片，兼容现有历史列表、预览和旧数据。

`extracted_data` 扩展为可包含多图诊断信息。下面只展示结构，字段值必须来自真实 OCR 识别和人工确认，系统不预置任何药品示例数据：

```json
{
  "name": "<真实 OCR 识别出的药品名称>",
  "approval_number": "<真实 OCR 识别出的批准文号>",
  "manufacturer": "<真实 OCR 识别出的生产企业>",
  "specification": "<真实 OCR 识别出的规格>",
  "batch_number": "<真实 OCR 识别出的批号>",
  "production_date": "<真实 OCR 识别出的生产日期>",
  "expiry_date": "<真实 OCR 识别出的有效期>",
  "quantity": null,
  "confidence_estimated": true,
  "multi_image": {
    "image_count": 3,
    "merged_from_image_indexes": {
      "name": 1,
      "approval_number": 1,
      "manufacturer": 2,
      "batch_number": 3,
      "expiry_date": 3
    },
    "consistency": {
      "status": "review_required",
      "method": "llm_no_overlap",
      "review_required": true,
      "batch_confirm_allowed": false,
      "message": "多张图片缺少可交叉验证字段，AI 仅提供辅助意见，请人工核对所有照片后再确认入库。",
      "conflicts": [],
      "llm_judgement": {
        "same_drug": "likely",
        "confidence": 0.68,
        "reason": "OCR 文本未发现冲突，但也缺少共同字段，只能作为可能同一药品的辅助判断。",
        "risk_notes": ["缺少批准文号或药品名称的跨图一致证据"]
      }
    }
  }
}
```

### 4.2 新增 `ocr_record_images`

新增子表保存每张图片级别的证据。

字段建议：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | int | 主键 |
| `ocr_record_id` | int | 外键，关联 `ocr_records.id` |
| `image_path` | string(500) | 图片相对路径，如 `ocr/<uuid>.jpg` |
| `image_index` | int | 上传顺序，从 1 开始 |
| `raw_text` | text nullable | 单图 OCR 原始文本 |
| `extracted_data` | json nullable | 单图结构化字段 |
| `confidence` | float nullable | 单图字段完整度 |
| `status` | enum/string | `pending` / `success` / `failed` |
| `error_message` | string(500) nullable | 单图失败原因 |
| `created_at` / `updated_at` | datetime | 时间戳 |

关系：一个 `OcrRecord` 有多条 `OcrRecordImage`。

删除 OCR 主记录时级联删除图片子记录。实际图片文件第一版可沿用现有行为，不强制物理删除，保持与当前系统一致。

## 5. API 设计

### 5.1 上传接口

保留现有路径：

```
POST /api/v1/ocr/upload
```

请求从单文件扩展为多文件：

- 字段名：`files`
- 类型：`list[UploadFile]`
- 兼容：若前端或旧调用仍传 `file`，后端可作为单图上传处理。

限制：

- 允许 1 至 `MAX_OCR_IMAGES_PER_RECORD` 张。
- 每张图片仍受 `MAX_UPLOAD_SIZE_MB` 限制。
- 每张图片 MIME 类型仍限制为 JPG / PNG / BMP / WebP。

响应仍返回 `OcrRecordResponse`，但响应模型增加：

- `image_paths: list[str]`
- `images: list[OcrRecordImageResponse]`

前端旧列表可继续使用 `image_path` 作为封面，新多图页面使用 `images` 展示缩略图组。

### 5.2 获取记录

```
GET /api/v1/ocr/{record_id}
```

返回主记录和所有图片子记录，按 `image_index` 排序。

### 5.3 列表接口

```
GET /api/v1/ocr
```

列表继续分页返回主记录。为避免列表 payload 太大，第一版可以只返回：

- `image_path`
- `image_paths`
- `image_count`
- `extracted_data.multi_image.consistency.status`
- `extracted_data.multi_image.consistency.review_required`

详情页再拉取完整 `images`。

## 6. 多图识别流水线

### 6.1 创建任务

`create_upload_record` 扩展为多图版本：

1. 校验所有文件类型和大小。
2. 保存所有图片到 `uploads/ocr/`。
3. 创建一条 `OcrRecord(status=pending, image_path=第一张路径)`。
4. 创建 N 条 `OcrRecordImage(status=pending)`。
5. 提交事务。
6. 后台任务接收 `record_id`，从磁盘读取或使用上传时保留的 bytes 逐张识别。

### 6.2 单图识别

复用当前：

```
recognize_and_extract(image_bytes) -> RecognitionResult
```

每张图识别后写入对应 `ocr_record_images`：

- `raw_text`
- `extracted_data`
- `confidence`
- `status`
- `error_message`

### 6.3 汇总识别

所有图片识别完成后执行：

1. 收集成功图片的结构化字段。
2. 执行规则一致性校验。
3. 如果规则判定失败，主记录 `status=failed`。
4. 如果规则判定通过或需要人工审核，合并字段，主记录 `status=success`。
5. 如果所有图片 OCR 都失败，主记录 `status=failed`。

## 7. 一致性校验设计

### 7.1 字段分级

强身份字段：

- `approval_number`
- `name`
- `manufacturer`
- `specification`

批次字段：

- `batch_number`
- `production_date`
- `expiry_date`

辅助字段：

- `quantity`

### 7.2 冲突规则

对每个字段，收集所有非空值并归一化后比较。

归一化规则：

- 去空格、全角半角规整、统一大小写。
- 日期统一成 `YYYY-MM-DD`。
- 批准文号移除空格和常见 OCR 分隔符。
- 药名保留中文主体，去除常见标点。

判定：

- `approval_number` 出现两个不同非空值：直接失败。
- `name` 出现明显不同非空值：直接失败。
- `manufacturer` 与 `specification` 同时冲突：直接失败。
- `batch_number` / `production_date` / `expiry_date` 出现冲突：失败，提示“疑似不同批次或不同药盒”。
- 只有辅助字段冲突不直接失败，进入人工审核提示。

### 7.3 一致锚点规则

存在以下任一情况，且没有冲突，则规则通过：

- 至少两张图都识别出相同 `approval_number`。
- 至少两张图都识别出相同 `name`。
- 至少两张图的 `manufacturer + specification` 组合一致。
- 一张图包含 `name`，另一张图包含相同 `approval_number` 对应的药品信息；第一版没有药品知识库时不启用此规则。

规则通过后仍要求用户确认入库，但不强制人工审核提示。

### 7.4 无重叠字段规则

如果不存在冲突，也不存在可交叉验证的一致锚点，则进入“无重叠字段”分支。

该分支调用 DeepSeek V4 Pro，但结论只作为辅助：

- LLM 认为不一致：主记录失败，提示疑似不同药盒。
- LLM 认为可能一致或不确定：主记录成功，但必须标记人工审核。
- LLM 调用失败：主记录成功，但必须标记人工审核，并提示“AI 辅助校验失败，请人工核对”。

## 8. DeepSeek 辅助校验器

### 8.1 配置

新增配置项：

```
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_TIMEOUT_SECONDS=30
```

LLM 校验仅在“无重叠字段”分支触发，避免每次上传都增加成本和延迟。

### 8.2 输入

只传 OCR 文本和结构化字段，不传原图：

```json
{
  "task": "判断这些 OCR 文本是否可能来自同一种药品盒子的不同包装面",
  "rules": [
    "你只是辅助判断，不能替代人工审核",
    "如果证据不足，请返回 uncertain",
    "不要编造图片中没有出现的信息",
    "发现疑似不同药品、不同规格、不同厂家、不同批次时要指出"
  ],
  "images": [
    {
      "image_index": 1,
      "raw_text": "<第1张图片真实 OCR 文本>",
      "fields": {
        "name": "<第1张图片识别出的药品名称>",
        "specification": "<第1张图片识别出的规格>"
      }
    },
    {
      "image_index": 2,
      "raw_text": "<第2张图片真实 OCR 文本>",
      "fields": {
        "manufacturer": "<第2张图片识别出的生产企业>",
        "expiry_date": "<第2张图片识别出的有效期>"
      }
    }
  ]
}
```

### 8.3 输出

强制 JSON：

```json
{
  "same_drug": "likely",
  "confidence": 0.68,
  "decision": "review",
  "reason": "未发现明确冲突，但 OCR 文本之间缺少可交叉验证的共同字段，只能判断为可能同一药品。",
  "evidence": ["第1张包含药品名称和规格", "第2张包含生产企业和有效期"],
  "risk_notes": ["缺少批准文号或药品名称的跨图一致证据"]
}
```

字段约束：

- `same_drug`: `likely` / `unlikely` / `uncertain`
- `confidence`: 0 到 1
- `decision`: `pass` / `review` / `fail`
- `reason`: 面向用户的简短解释
- `evidence`: 支持判断的 OCR 证据
- `risk_notes`: 需要人工关注的风险点

### 8.4 决策映射

| LLM 输出 | 系统结果 |
| --- | --- |
| `decision=fail` 或 `same_drug=unlikely` | 主记录 `failed`，不允许确认入库 |
| `decision=pass` 或 `same_drug=likely` | 主记录 `success`，但 `review_required=true` |
| `decision=review` 或 `same_drug=uncertain` | 主记录 `success`，但 `review_required=true` 且风险等级更高 |
| LLM 调用异常 | 主记录 `success`，但 `review_required=true`，提示 AI 辅助校验失败 |

安全底线：

- LLM 不能覆盖规则冲突。
- LLM 不能让记录跳过人工确认。
- LLM 不能让无重叠字段记录进入批量确认。

## 9. 字段合并策略

合并以“填补空缺”为主，不做复杂投票。

顺序：

1. 对每个字段收集所有非空候选值。
2. 如果只有一个候选值，直接使用。
3. 如果多个候选值归一化后一致，使用信息更完整的原始值。
4. 如果多个候选值冲突，按照一致性规则处理；未被规则拦截的辅助冲突写入 `conflicts`，并要求人工审核。
5. 记录每个字段来自第几张图，写入 `merged_from_image_indexes`。

`raw_text` 合并为带图片编号的文本：

```text
[图片1]
...

[图片2]
...
```

`confidence` 使用合并后字段完整度，并保留 `confidence_estimated=true`。

## 10. 前端交互设计

### 10.1 上传区

从单图预览改为多图缩略图列表：

- 支持点击选择多图。
- 支持拖拽多图。
- 支持删除单张缩略图。
- 显示顺序编号：第 1 张、第 2 张。
- 显示数量限制：最多 6 张，每张最大 10 MB。

按钮文案：

- 单图或多图均为“开始识别”。
- 上传中显示“上传中...”。

### 10.2 结果区

结果面板新增：

- 多图缩略图组，可预览大图。
- 字段来源标记，例如“来自第 3 张”。
- 一致性状态提示。

状态提示：

- 规则通过：普通待确认。
- 规则冲突：错误提示，禁用确认入库。
- 无重叠字段 + LLM 辅助：醒目警告。

警告文案：

> 多张图片缺少可交叉验证字段，AI 仅提供辅助判断。请人工核对所有照片、OCR 文本和字段来源后再确认入库。

确认按钮在人工审核场景改为：

> 已人工核对，确认入库

### 10.3 批量确认限制

如果 `extracted_data.multi_image.consistency.review_required=true`：

- 入库任务队列和历史记录中该行不允许被批量确认。
- 批量确认时跳过该记录，并提示“存在需要人工审核的多图记录，请单独打开确认”。
- 单独打开详情后才允许确认。

## 11. 后端状态与错误处理

继续复用现有主状态：

- `pending`: 多图任务创建后，识别中。
- `success`: 多图识别完成，可进入确认流程。可能包含 `review_required=true`。
- `failed`: OCR 全部失败、明确字段冲突、LLM 辅助判断为不一致，或上传校验失败。
- `confirmed`: 用户确认入库后。

不新增 `needs_review` 枚举，避免扩大数据库枚举迁移和前端状态映射范围。人工审核通过 `extracted_data.multi_image.consistency.review_required` 表达。

错误信息策略：

- 明确冲突：`error_message` 写清字段、图片序号和值。
- LLM 判断不一致：`error_message` 写清 LLM reason 和 risk notes。
- LLM 调用失败但无规则冲突：不让主记录失败，写入 `consistency.llm_error` 并要求人工审核。

## 12. 文件改动清单

### 后端新增

| 文件 | 职责 |
| --- | --- |
| `backend/app/models/ocr_record_image.py` | OCR 多图子记录模型 |
| `backend/app/ocr/multi_image_consistency.py` | 字段归一化、冲突检测、一致锚点判断、字段合并 |
| `backend/app/ocr/deepseek_consistency_client.py` | DeepSeek V4 Pro 辅助校验客户端 |
| `backend/alembic/versions/<revision>_add_ocr_record_images.py` | 新增子表和必要索引 |
| `backend/tests/test_multi_image_consistency.py` | 规则校验和合并策略单测 |
| `backend/tests/test_deepseek_consistency_client.py` | DeepSeek 请求构造、JSON 解析和异常兜底单测 |

### 后端修改

| 文件 | 改动 |
| --- | --- |
| `backend/app/models/ocr_record.py` | 增加 relationship，保留 `image_path` |
| `backend/app/models/__init__.py` | 导入新模型供 Alembic 发现 |
| `backend/app/schemas/ocr.py` | 增加多图响应 schema |
| `backend/app/api/v1/ocr.py` | 上传接口支持 `files`，兼容旧 `file` |
| `backend/app/services/ocr_service.py` | 拆分单图保存、多图保存、后台多图识别、汇总合并 |
| `backend/app/config.py` | 增加最大图片数和 DeepSeek 辅助校验配置 |
| `.env.example` / `backend/.env.example` | 增加新配置 |
| `docker-compose.yml` | 透传新环境变量 |
| `backend/tests/test_ocr_service.py` | 覆盖多图记录创建、冲突失败、人工审核标记 |

### 前端修改

| 文件 | 改动 |
| --- | --- |
| `frontend/src/types/ocr.ts` | 增加 `image_paths`、`images`、`multi_image` 类型 |
| `frontend/src/api/ocr.ts` | 上传 FormData 支持多个 `files` |
| `frontend/src/stores/ocr.ts` | `uploadAndRecognize` 接收 `File[]`，批量确认跳过人工审核记录 |
| `frontend/src/views/ocr/OcrUploadView.vue` | 多图选择、缩略图组、字段来源、一致性警告、人工审核确认按钮 |

## 13. 测试策略

### 后端单测

规则校验：

- 相同批准文号通过。
- 不同批准文号失败。
- 药名明显冲突失败。
- 批号冲突失败并提示不同批次或不同药盒。
- 无冲突且无重叠字段触发 LLM 分支。
- LLM 返回 likely 时标记 `review_required=true`。
- LLM 返回 unlikely 时主记录失败。
- LLM 调用异常时主记录成功但强制人工审核。

字段合并：

- 不同图片字段互补时合并成完整数据。
- 记录每个字段来源图片序号。
- 合并 raw_text 时保留图片编号。

服务层：

- 多图上传创建一条主记录和多条图片子记录。
- 单图旧接口仍可工作。
- 后台识别部分图片失败时，成功图片仍参与汇总；若可用证据不足则要求人工审核。

### 前端验证

- 选择多张图后缩略图显示正确。
- 可删除单张待上传图片。
- 上传成功后任务队列显示封面和图片数量。
- 人工审核记录不能批量确认。
- 打开人工审核记录时显示 AI 辅助提示和“已人工核对，确认入库”。
- 冲突失败记录禁用确认。

### 回归验证命令

后端：

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
```

前端：

```powershell
cd frontend
npm run build
```

## 14. 用户可见行为示例

### 14.1 正常多面合并

用户上传：

- 第 1 张：药品名称、批准文号、规格。
- 第 2 张：生产企业。
- 第 3 张：批号、生产日期、有效期。

系统行为：

- 逐张 OCR。
- 无冲突，有名称和批准文号作为身份锚点。
- 合并成一条待确认记录。
- 前端显示字段来源。

### 14.2 明确不同药盒

用户上传：

- 第 1 张：批准文号 A。
- 第 2 张：批准文号 B。

系统行为：

- 规则直接失败。
- 前端提示：“第 1 张和第 2 张批准文号不一致，疑似不同药盒。请只上传同一药盒的不同面。”
- 禁用确认入库。

### 14.3 无重叠字段

用户上传：

- 第 1 张：药品名称和规格。
- 第 2 张：生产企业和有效期。
- 第 3 张：储存条件和条形码。

系统行为：

- 规则没有发现冲突，也没有足够重叠字段确认一致。
- 调用 DeepSeek V4 Pro 辅助判断。
- 如果 LLM 认为可能一致，主记录进入待确认，但标记 `review_required=true`。
- 前端提示必须人工审核，且不能批量确认。

## 15. 风险与取舍

- 无重叠字段本质上无法被系统严格证明为同一药盒。DeepSeek 的作用是给出辅助解释和风险点，不是最终裁决。
- 将人工审核标记放在 `extracted_data` 中，而不是新增主状态，能减少对现有状态机的冲击，但前端和批量确认必须严格读取该标记。
- 第一版不做视觉相似度，可能无法发现“文本看似可拼接但图片明显不是同一包装风格”的情况。该能力可作为后续增强。
- 多图逐张 OCR 会增加识别耗时和 Qwen OCR 调用成本，因此需要最大图片数限制。

## 16. 验收标准

- 用户可以一次上传多张同一药盒不同面的照片。
- 系统只生成一条 OCR 主记录，并保存每张图片的 OCR 证据。
- 多图字段可以合并为一份确认表单。
- 明确字段冲突时不能确认入库。
- 无重叠字段时会调用 DeepSeek V4 Pro 辅助判断。
- DeepSeek 只提供辅助意见，前端必须提示人工审核。
- 需要人工审核的记录不能批量确认，只能单独打开后确认。
- 单图上传、历史记录、确认入库、删除记录的现有行为不回归。
