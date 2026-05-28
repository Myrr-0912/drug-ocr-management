# OCR Pause Resume Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a pause button for OCR task queue records that are still recognizing, plus a resume action for paused records.

**Architecture:** Add a persisted `paused` OCR status so pause survives refreshes. The API exposes pause/resume endpoints; background recognition checks the persisted status before each image and before writing OCR results. The frontend shows pause/resume actions in the task queue and includes paused tasks in queue loading.

**Tech Stack:** FastAPI, SQLAlchemy async ORM, Alembic/MySQL, Pinia, Vue 3, Element Plus.

---

### Task 1: Backend Pause State and Recognition Checkpoints

**Files:**
- Modify: `backend/app/models/ocr_record.py`
- Modify: `backend/app/services/ocr_service.py`
- Modify: `backend/tests/test_ocr_service.py`
- Create: `backend/alembic/versions/2c8f4e6a9b31_add_paused_ocr_status.py`

- [ ] **Step 1: Write failing service tests**

Add tests that expect `OcrStatus.paused`, `pause_record`, `resume_record`, and recognition abort-on-pause behavior:

```python
async def test_pause_record_marks_pending_record_and_images_paused():
    record = OcrRecord(id=20, image_path="ocr/a.jpg", status=OcrStatus.pending)
    record.images = [
        OcrRecordImage(id=1, image_path="ocr/a.jpg", image_index=1, status=OcrStatus.pending),
        OcrRecordImage(id=2, image_path="ocr/b.jpg", image_index=2, status=OcrStatus.success),
    ]

    result = await ocr_service.pause_record(db=_FakeSession(record), record_id=20)

    assert result.status == OcrStatus.paused
    assert record.images[0].status == OcrStatus.paused
    assert record.images[1].status == OcrStatus.success
```

```python
async def test_resume_record_marks_paused_record_and_images_pending():
    record = OcrRecord(id=21, image_path="ocr/a.jpg", status=OcrStatus.paused)
    record.images = [
        OcrRecordImage(id=1, image_path="ocr/a.jpg", image_index=1, status=OcrStatus.paused),
    ]

    result = await ocr_service.resume_record(db=_FakeSession(record), record_id=21)

    assert result.status == OcrStatus.pending
    assert record.images[0].status == OcrStatus.pending
    assert result.error_message is None
```

```python
async def test_recognize_record_images_aborts_when_record_pauses_before_write(monkeypatch):
    record = OcrRecord(id=22, image_path="ocr/a.jpg", status=OcrStatus.pending)
    record.images = [OcrRecordImage(id=1, image_path="ocr/a.jpg", image_index=1, status=OcrStatus.pending)]
    db = _PauseAfterSecondStatusRefreshSession(record)
    monkeypatch.setattr(ocr_service, "recognize_and_extract", AsyncMock(return_value=RecognitionResult(
        raw_text="真实 OCR 文本",
        extracted=ExtractedDrugData(name="药品甲"),
        confidence=0.12,
    )))

    await ocr_service.recognize_record_images(db=db, record=record, image_bytes_list=[b"image"])

    assert record.status == OcrStatus.paused
    assert record.raw_text is None
    assert record.images[0].raw_text is None
```

- [ ] **Step 2: Run tests to verify red**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_ocr_service.py -q`

Expected: FAIL because `paused`, `pause_record`, `resume_record`, and pause checkpoint behavior do not exist.

- [ ] **Step 3: Implement backend state and services**

Add `paused = "paused"` to `OcrStatus`. Implement `pause_record`, `resume_record`, and a status-refresh helper used by `recognize_record_images`. Pause only accepts `pending`; resume only accepts `paused`. During recognition, return immediately if the record is paused before processing an image or before writing a just-finished OCR result.

- [ ] **Step 4: Add Alembic migration**

Create a migration from `7f3b9c2a4d10` to alter MySQL enum columns:

```sql
ALTER TABLE ocr_records MODIFY status ENUM('pending','success','failed','confirmed','paused') NOT NULL;
ALTER TABLE ocr_record_images MODIFY status ENUM('pending','success','failed','confirmed','paused') NOT NULL;
```

Downgrade first maps `paused` rows back to `pending`, then restores the old enum.

- [ ] **Step 5: Verify backend tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_ocr_service.py -q`

Expected: PASS.

### Task 2: Pause and Resume API Endpoints

**Files:**
- Modify: `backend/app/api/v1/ocr.py`

- [ ] **Step 1: Add API endpoints**

Add:

```python
@router.post("/{record_id}/pause")
async def pause_record(...):
    record = await ocr_service.pause_record(db=db, record_id=record_id)
    await db.commit()
    return ok(OcrRecordResponse.model_validate(record), "识别任务已暂停")
```

```python
@router.post("/{record_id}/resume")
async def resume_record(...):
    record = await ocr_service.resume_record(db=db, record_id=record_id)
    image_bytes_list = ocr_service.load_record_image_bytes(record)
    await db.commit()
    background_tasks.add_task(ocr_service.recognize_record_images_background, record.id, image_bytes_list)
    return ok(OcrRecordResponse.model_validate(record), "识别任务已恢复")
```

- [ ] **Step 2: Verify backend tests**

Run: `.\.venv\Scripts\python.exe -m pytest -q`

Expected: PASS.

### Task 3: Frontend Queue Pause and Resume Controls

**Files:**
- Modify: `frontend/src/types/ocr.ts`
- Modify: `frontend/src/api/ocr.ts`
- Modify: `frontend/src/stores/ocr.ts`
- Modify: `frontend/src/views/ocr/OcrUploadView.vue`

- [ ] **Step 1: Update OCR status types**

Add `paused` to `OcrStatus` and `OCR_STATUS_MAP`.

- [ ] **Step 2: Add API wrappers and store actions**

Add `pauseOcrRecord(recordId)` and `resumeOcrRecord(recordId)` wrappers. Add Pinia actions `pauseRecord` and `resumeRecord` that update queue/history state. Include `paused` in `loadTaskQueue`.

- [ ] **Step 3: Add task queue buttons**

In the task queue operation column, show `暂停` when `row.status === 'pending'` and `继续` when `row.status === 'paused'`. `继续` should call resume, then start polling again via `watchQueueRecord(row.id)`.

- [ ] **Step 4: Verify frontend build**

Run: `npm run build`

Expected: PASS.

### Task 4: Final Verification

**Files:**
- No new files.

- [ ] **Step 1: Run backend test suite**

Run: `.\.venv\Scripts\python.exe -m pytest -q`

Expected: PASS.

- [ ] **Step 2: Run frontend build**

Run: `npm run build`

Expected: PASS.

- [ ] **Step 3: Summarize runtime note**

Tell the user they need to run `alembic upgrade head` and restart the backend so the new `paused` enum value is available.
