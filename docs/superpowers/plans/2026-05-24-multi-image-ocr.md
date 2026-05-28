# Multi-Image OCR Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement multi-image OCR upload so one drug box can be uploaded as multiple faces, merged into one OCR record, and guarded by rule-first consistency checks plus DeepSeek auxiliary review for no-overlap cases.

**Architecture:** Keep `ocr_records` as the task and confirmation root. Add `ocr_record_images` as child evidence rows, reuse the existing single-image `recognize_and_extract()` pipeline per image, then merge child OCR outputs through `multi_image_consistency.py`. Frontend continues to work with one active OCR record, but upload state becomes `File[]` and review-required records require explicit manual confirmation.

**Tech Stack:** FastAPI, SQLAlchemy async ORM, Alembic, Pydantic, pytest, Vue 3, Pinia, Element Plus, TypeScript.

---

## File Structure

- Create `backend/app/models/ocr_record_image.py`: child ORM model for each uploaded image.
- Modify `backend/app/models/ocr_record.py`: relationship to child images, keeping `image_path` as the cover path.
- Modify `backend/app/models/__init__.py`: import the new model for Alembic.
- Create `backend/alembic/versions/7f3b9c2a4d10_add_ocr_record_images.py`: creates the child table and indexes.
- Create `backend/app/ocr/multi_image_consistency.py`: pure functions for normalization, conflict detection, merge, and review metadata.
- Create `backend/app/ocr/deepseek_consistency_client.py`: OpenAI-compatible DeepSeek V4 Pro JSON client.
- Modify `backend/app/config.py`, `.env.example`, `backend/.env.example`, `docker-compose.yml`: maximum image count and DeepSeek settings.
- Modify `backend/app/schemas/ocr.py`: child image response and multi-image fields on `OcrRecordResponse`.
- Modify `backend/app/services/ocr_service.py`: multi-image save/recognize/merge functions while preserving single-image API helpers.
- Modify `backend/app/api/v1/ocr.py`: accept `files` while keeping old `file` compatibility.
- Create `backend/tests/test_multi_image_consistency.py`: pure logic coverage.
- Create `backend/tests/test_deepseek_consistency_client.py`: request and response behavior.
- Modify `backend/tests/test_ocr_service.py`: multi-image service behavior.
- Modify `frontend/src/types/ocr.ts`: child image and review metadata types.
- Modify `frontend/src/api/ocr.ts`: append multiple `files`.
- Modify `frontend/src/stores/ocr.ts`: `uploadAndRecognize(files: File | File[])`, batch-confirm guard.
- Modify `frontend/src/views/ocr/OcrUploadView.vue`: multi-thumbnail upload and review-required UI.

## Task 1: Consistency Rules

**Files:**
- Create: `backend/app/ocr/multi_image_consistency.py`
- Create: `backend/tests/test_multi_image_consistency.py`

- [ ] **Step 1: Write failing tests for rule-first consistency**

Create tests covering approval-number conflict, complementary merge, no-overlap review, and failed LLM result:

```python
from app.ocr.multi_image_consistency import (
    ImageOcrEvidence,
    LlmConsistencyJudgement,
    evaluate_multi_image_consistency,
)


def test_approval_number_conflict_fails():
    result = evaluate_multi_image_consistency([
        ImageOcrEvidence(image_index=1, raw_text="A", fields={"approval_number": "国药准字A"}),
        ImageOcrEvidence(image_index=2, raw_text="B", fields={"approval_number": "国药准字B"}),
    ])

    assert result.status == "failed"
    assert result.review_required is False
    assert result.conflicts[0]["field"] == "approval_number"


def test_complementary_fields_merge_with_review_when_no_overlap():
    result = evaluate_multi_image_consistency([
        ImageOcrEvidence(image_index=1, raw_text="名称", fields={"name": "药品甲"}),
        ImageOcrEvidence(image_index=2, raw_text="有效期", fields={"expiry_date": "2026-01-01"}),
    ])

    assert result.status == "review_required"
    assert result.review_required is True
    assert result.batch_confirm_allowed is False
    assert result.merged_fields["name"] == "药品甲"
    assert result.merged_from_image_indexes["name"] == 1
    assert "[图片1]" in result.raw_text


def test_same_approval_number_passes_without_review():
    result = evaluate_multi_image_consistency([
        ImageOcrEvidence(image_index=1, raw_text="批准文号", fields={"approval_number": "国药准字H1"}),
        ImageOcrEvidence(image_index=2, raw_text="批准文号", fields={"approval_number": "国药准字 H1"}),
    ])

    assert result.status == "passed"
    assert result.review_required is False
    assert result.merged_fields["approval_number"] == "国药准字H1"


def test_no_overlap_llm_unlikely_fails():
    result = evaluate_multi_image_consistency(
        [
            ImageOcrEvidence(image_index=1, raw_text="名称", fields={"name": "药品甲"}),
            ImageOcrEvidence(image_index=2, raw_text="厂家", fields={"manufacturer": "厂家乙"}),
        ],
        llm_judgement=LlmConsistencyJudgement(
            same_drug="unlikely",
            confidence=0.8,
            decision="fail",
            reason="疑似不同药品",
            evidence=[],
            risk_notes=["缺少共同字段"],
        ),
    )

    assert result.status == "failed"
    assert "疑似不同药品" in result.message
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_multi_image_consistency.py -q
```

Expected: fails with `ModuleNotFoundError` or missing names from `app.ocr.multi_image_consistency`.

- [ ] **Step 3: Implement `multi_image_consistency.py`**

Implement dataclasses:

```python
@dataclass
class ImageOcrEvidence:
    image_index: int
    raw_text: str
    fields: dict[str, Any]

@dataclass
class LlmConsistencyJudgement:
    same_drug: Literal["likely", "unlikely", "uncertain"]
    confidence: float
    decision: Literal["pass", "review", "fail"]
    reason: str
    evidence: list[str]
    risk_notes: list[str]

@dataclass
class MultiImageConsistencyResult:
    status: Literal["passed", "review_required", "failed"]
    method: str
    review_required: bool
    batch_confirm_allowed: bool
    message: str
    conflicts: list[dict[str, Any]]
    merged_fields: dict[str, Any]
    merged_from_image_indexes: dict[str, int]
    raw_text: str
    llm_judgement: dict[str, Any] | None = None
    llm_error: str | None = None
```

Implement `evaluate_multi_image_consistency(evidence, llm_judgement=None, llm_error=None)` with the spec rules. Use no network calls in this module.

- [ ] **Step 4: Verify Task 1**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_multi_image_consistency.py -q
```

Expected: all tests in the file pass.

## Task 2: DeepSeek Auxiliary Client

**Files:**
- Create: `backend/app/ocr/deepseek_consistency_client.py`
- Create: `backend/tests/test_deepseek_consistency_client.py`
- Modify: `backend/app/config.py`
- Modify: `.env.example`
- Modify: `backend/.env.example`
- Modify: `docker-compose.yml`

- [ ] **Step 1: Write failing tests**

Test that missing API key raises a clear error, valid JSON is parsed, invalid JSON becomes an uncertain judgement, and the configured model is sent.

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_deepseek_consistency_client.py -q
```

Expected: fails because the client module does not exist.

- [ ] **Step 3: Add config fields**

Add to `Settings`:

```python
max_ocr_images_per_record: int = 6
deepseek_api_key: str = ""
deepseek_base_url: str = "https://api.deepseek.com"
deepseek_model: str = "deepseek-v4-pro"
deepseek_timeout_seconds: int = 30
```

Add matching env example keys.

- [ ] **Step 4: Implement client**

Use `httpx.AsyncClient` and `POST {deepseek_base_url}/chat/completions`. Return `LlmConsistencyJudgement`. On missing key raise `RuntimeError("未配置 DEEPSEEK_API_KEY，无法进行多图一致性辅助校验")`. On parse failure return `same_drug="uncertain"`, `decision="review"`.

- [ ] **Step 5: Verify Task 2**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_deepseek_consistency_client.py tests/test_config.py -q
```

Expected: all selected tests pass.

## Task 3: ORM, Migration, and Schemas

**Files:**
- Create: `backend/app/models/ocr_record_image.py`
- Create: `backend/alembic/versions/7f3b9c2a4d10_add_ocr_record_images.py`
- Modify: `backend/app/models/ocr_record.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/schemas/ocr.py`

- [ ] **Step 1: Write schema/model tests in service tests**

Add a test that creates an `OcrRecord` with two child images and validates `OcrRecordResponse` includes `image_paths`, `image_count`, and ordered `images`.

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_ocr_service.py::test_ocr_record_response_includes_child_images -q
```

Expected: fails because child model and schema fields do not exist.

- [ ] **Step 3: Implement model and schema**

`OcrRecordImage` columns match the design. Use `relationship(..., cascade="all, delete-orphan")`. Add Pydantic `OcrRecordImageResponse` and computed response fields through normal attributes/properties on model or schema defaults.

- [ ] **Step 4: Add Alembic migration**

Create table `ocr_record_images` with FK `ocr_record_id -> ocr_records.id ON DELETE CASCADE`, indexes on `ocr_record_id` and `(ocr_record_id, image_index)`.

- [ ] **Step 5: Verify Task 3**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_ocr_service.py -q
```

Expected: OCR service tests pass.

## Task 4: Multi-Image OCR Service and API

**Files:**
- Modify: `backend/app/services/ocr_service.py`
- Modify: `backend/app/api/v1/ocr.py`
- Modify: `backend/tests/test_ocr_service.py`

- [ ] **Step 1: Write failing service tests**

Cover:

- `create_upload_record_multi` creates one record and N child images.
- `recognize_record_images` writes child OCR results and merged parent data.
- explicit conflicts mark parent `failed`.
- no-overlap with LLM likely marks parent `success` and `review_required=true`.
- bad content type in any file rejects the whole upload.

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_ocr_service.py -q
```

Expected: new tests fail because multi-image helpers do not exist.

- [ ] **Step 3: Implement service**

Add:

```python
async def create_upload_record_multi(db, files, operator_id) -> OcrRecord
async def recognize_record_images(db, record, image_payloads, llm_judgement=None) -> OcrRecord
async def recognize_record_images_background(record_id, image_payloads) -> None
```

Keep `create_upload_record` and `recognize_record_background` as single-image compatibility wrappers.

- [ ] **Step 4: Implement API compatibility**

`POST /ocr/upload` accepts `files: list[UploadFile] | None = File(None)` and `file: UploadFile | None = File(None)`. If both are empty, raise `BusinessError("请至少上传一张图片")`. If both are present, combine with `files` first then `file`.

- [ ] **Step 5: Verify Task 4**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_ocr_service.py tests/test_multi_image_consistency.py tests/test_deepseek_consistency_client.py -q
```

Expected: selected backend tests pass.

## Task 5: Frontend Multi-Image Upload and Review Guard

**Files:**
- Modify: `frontend/src/types/ocr.ts`
- Modify: `frontend/src/api/ocr.ts`
- Modify: `frontend/src/stores/ocr.ts`
- Modify: `frontend/src/views/ocr/OcrUploadView.vue`

- [ ] **Step 1: Update types and API**

Add `OcrRecordImage`, `MultiImageConsistency`, and `isReviewRequired(record)` helper logic. `uploadAndRecognize` accepts `File | File[]` and appends each item as `files`.

- [ ] **Step 2: Update upload UI**

Replace `selectedFile` with `selectedFiles`. Render thumbnails with remove buttons and image indexes. Keep single image upload working by treating it as an array of one.

- [ ] **Step 3: Update review UI**

Show multi-image thumbnails for `currentRecord.images`. Show warning alert for `review_required`. Change confirm button text to `已人工核对，确认入库` when review is required.

- [ ] **Step 4: Update batch confirm guard**

Skip records with `extracted_data.multi_image.consistency.review_required === true` and include them in the skipped count.

- [ ] **Step 5: Verify Task 5**

Run:

```powershell
cd frontend
npm run build
```

Expected: TypeScript and Vite build succeed.

## Task 6: Final Verification

**Files:**
- All modified files above.

- [ ] **Step 1: Run full backend tests**

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: all backend tests pass.

- [ ] **Step 2: Run frontend build**

```powershell
cd frontend
npm run build
```

Expected: build succeeds.

- [ ] **Step 3: Search for fake OCR examples**

```powershell
Get-ChildItem -Path backend,frontend,docs -Recurse -File |
  Where-Object { $_.FullName -notmatch '\\.venv|node_modules|dist|__pycache__' } |
  Select-String -Pattern '返回 mock|使用 mock|_mock_response'
```

Expected: no matches.
