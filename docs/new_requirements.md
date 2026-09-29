Here is the **complete, finalized plan** consolidating every decision we've locked in — backend + frontend.

---

# FINAL PLAN — Backend + Frontend Integration

## 1. Target end‑to‑end flow

```
1  LOGIN / SIGNUP ......... extension UI → POST /auth/token | /auth/register
                           → store accessToken (chrome.storage.local); load /reports/user

2  OPEN REPORT ............ match active tab URL → resolve/create backend report
                           (POST /reports with source_url) → store report_id

3  SCAN ................... content scans form → render schema table LOCALLY
                           → POST /reports/{id}/form_schema
                             payload: { form_schema, scanned_payload, trigger_intent:true }
                           → backend stores schema + scanned payload (DB)
                           → INTENT PRE-PASS runs in parallel (openquire-URL guard)

4  UPLOAD ................. pick files; split into PDF vs IMAGE lists
                           → POST /reports/{id}/upload/pdf   (doc_types: scanned|handwritten)
                           → POST /reports/{id}/upload/image (images + zip, pdfs-in-zip ignored)
                           each → {status:"processing", job_id}  (non-blocking)
                           per-file: file-hash DEDUP + extraction_status in File.meta
                           → Process & Map button ENABLED once ≥1 document uploaded

5  PROCESS & MAP .......... single button → (re)upload pending files → POST /reports/{id}/map
                           → {status:"processing", job_id} (NON-BLOCKING, no error shown)
                           backend map_task waits for BOTH gates:
                             (a) are_all_files_completed
                             (b) are_intents_ready
                           → run_mapping → save results → job completed → mapping_done
                           → EMAIL user "Mapping complete — ready for verification"

6  VERIFY ................. on panel open: GET /reports/jobs/{job_id} + GET /reports/{id}/mapping
                           → refresh mapping table when job = completed

7  SUBMIT ................. "Submit" → fill real web form (content autoFill)
                           → POST /reports/{id}/form_schema { filled form_schema, trigger_intent:false }
                           → stored (marked final)
```

---

## 2. Data & storage model (final)

| Data                | Where                                                                                       | Notes                                                         |
| ------------------- | ------------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| `form_schema`       | **DB** — `form_schemas` (upsert, bump `version`)                                            | Not storage (storage is legacy)                               |
| `scanned_payload`   | **DB** — new `FormSchema.scanned_payload` JSON column (with migration)                      | sent at scan                                                  |
| intents             | **DB** — new `report_intents` table (source of truth) + **Redis `set_intent`** (fast cache) | per `(report_id, section_id)` row avoids parallel-write races |
| per-file sub-status | **DB** — `File.meta` JSON (`extraction_status`) + aggregate `File.status`                   | **no** embedding status (excluded)                            |
| report aggregate    | computed live by helper                                                                     | no schema change                                              |

**New table** `report_intents(id, report_id FK, section_id, section_name, field_count, intent JSON, status "pending"|"completed"|"failed", created_at, updated_at)`
**New column** `form_schemas.scanned_payload JSON nullable`

---

## 3. Backend changes (exact files)

### 3a. `inspection_ai/database/repositories/report_repository.py`

Add (no‑underscore names):

- `get_file_by_hash(report_id, file_hash)` — dedup
- `update_file_extraction_state(report_id, filename, *, extraction_status, error=None)` — writes `File.meta` + `File.status`
- `are_all_files_completed(report_id)` — **gate (a)**
- `get_report_processing_status(report_id)` → `{total_documents, filenames, extraction_completed, mapping_done, intent_status}`
- `save_section_intent(...)`, `are_intents_ready(report_id, section_count)`, `get_intents(report_id)` — **gate (b)**
- `get_user_email(user_id)` — email recipient
- Modify `save_form_schema` → upsert + accept/store `scanned_payload`
- Modify `save_mapping_results` → replace prior rows for the report

### 3b. `inspection_ai/api/report_routes.py`

- **NEW** `POST /reports/{id}/form_schema` — accepts `{form_schema, scanned_payload, trigger_intent}`; stores both; guarded intent pre-pass; returns stored/processing
- **NEW** `GET /reports/{id}/form_schema` — readback `{form_schema, scanned_payload}`
- **NEW** `GET /reports/{id}/mapping` — latest `MappingResult` + `mapping_done` + job status
- **Modify** `upload_pdf` (253–475) — dedup, per-file extraction status, return `"processing"`
- **Modify** `upload_image` (476–695) — dedup, ignore PDFs in ZIP (~503–505), per-file status, return `"processing"`
- **Modify** `map_report_fields` (697–782) — refactor core into reusable `run_mapping(...)`; endpoint becomes async job trigger (create map job → `map_task.delay`; no-broker → inline); return `{status:"processing", job_id}`
- Rename `_parse_doc_types`/`_get_services` → `parse_doc_types`/`get_services`

### 3c. New tasks

- `inspection_ai/tasks/intent_task.py` — `process_reported_intents(report_id, user_id, section_count)` — normalize schema → run section intents in PARALLEL (semaphore) → `save_section_intent` + Redis → job completed (try/except logs `report_id`)
- `inspection_ai/tasks/map_task.py` — `map_when_ready(job_id, report_id, user_id)` — bounded wait gates (a)+(b) → `run_mapping` → save → job completed → `mapping_done` → **`send_email`** (try/except; email failures don't fail job)

### 3d. `pdf_task.py` / `image_task.py`

- Keep extraction/embedding logic + Celery registration as-is
- **REMOVE** the two existing `send_email` calls (+ now-unused `_recipient` helper)
- Add per-file `extraction_status` updates
- Rename underscore helpers only where touched

### 3e. `universal_service/indexer/vector_store.py` (optional, keep)

- `encode_and_store` (379–401): replace `delete_by_scope`+store-all with **hash-based delta skip** (don't re-upsert already-indexed chunks)

### 3f. `inspection_ai/celery_app.py`

- Register `intent_task` + `map_task` (line ~41 pattern)

### 3g. Migration

- Add `report_intents` table + `form_schemas.scanned_payload` column

**Explicitly NOT changed (core):** `LLMClient`, `UniversalMapper.map_form`, `PDFExtractor`, `ImageExtractor`, `HandwrittenExtractor`, `normalize_form_schema`, `MappingHandler.build_results`, auth, evidence/embedding core.

---

## 4. Email handling (final)

- **Removed:** `send_email` from `pdf_task`/`image_task`.
- **Added (mapping success only):** in `map_task`, after job `completed`/`mapping_done`:
  `send_email(to_email=get_user_email(user_id), subject="Mapping complete — ready for verification", body=f"Report {report_id}: mapping finished, ready for verification.")`
  Fallback to `user_id@email_domain` if no real email; try/except + log; never fails the job.

---

## 5. Frontend changes (exact files)

### 5a. `openquire-ai-extension/background/background.js`

- Add `apiLogin`, `apiSignup` (store token), `apiCreateReport`(`POST /reports` with URL); reuse `getActiveReport` URL-match
- `storeFormSchema(reportId, {form_schema, scanned_payload}, trigger_intent)` → `POST /reports/{id}/form_schema`
- `getFormSchema` → `GET /reports/{id}/form_schema`
- `scanForm` handler → render locally + createReport + POST form_schema (schema + scanned payload)
- `apiUploadPdf`/`apiUploadImage` → parse `{status:"processing", job_id}`; store job_id; non-blocking
- New handler **Process & Map** → upload pending PDF list → upload IMAGE list → `POST /reports/{id}/map` (async-aware), store `mapJobId`
- `apiGetJobStatus(job_id)` → `GET /reports/jobs/{job_id}`
- `apiGetMappingResults(reportId)` → `GET /reports/{id}/mapping`
- **Submit** handler → content `autoFill` → `storeFormSchema(reportId, filledSchema, trigger_intent:false)`

### 5b. `ui/src/lib/messaging.ts`

- Add `login`, `signup`, `createReport`, `storeFormSchema`, `getJobStatus`, `getMappingResults`, `processAndMap`, `submitForm`
- `uploadMultipleFiles` → route PDF vs IMAGE to the two endpoints separately; return job info (non-blocking)

### 5c. `ui/src/store/useStore.ts`

- Add auth (`isAuthenticated`, `email`, `accessToken`), `reportId`, `docJobs`, `mapJobId`, `jobStatus` (`idle|processing|completed|failed`), `mappingDone`, `isProcessing`, `isSubmitting`

### 5d. Components (new/updated)

- **`LoginSection.tsx` (new)** — signup + login
- **`ActionsSection.tsx`** → **Scan Form** · **Process & Map** (single button; disabled until scanned + ≥1 doc; non-blocking; "you'll be emailed when ready") · **Submit** (disabled until mapping done)
- **`DocumentsSection.tsx`/`Drawer.tsx`** — two-endpoint upload, per-job "processing" state, enable map button
- **`FormStatusSection.tsx`/`FormFieldsTable.tsx`** — local scanned table (fields/values/options) + refresh from mapping when job completed
- **`ActivitySection.tsx`** — log auth/scan/upload/map/submit

### 5e. `content/content.js`

- Keep `scanForm` + `autoFill`; add `submitFill` path ("fill then store"); handle new `submitForm` action

### 5f. Rebuild

- `cd ui && npm run build` → regenerate `openquire-ai-extension/ui/dist/*` (side panel uses the built bundle)

---

## 6. Code rules (applied throughout)

- No method starts with `_` (rename the small set of orchestration helpers we touch)
- `try/except` + logs including `file=<name>` / `report=<id>` in all modified paths
- SOLID / loose coupling / KISS / no over-engineering; small additive helpers; no globals

---

## 7. Build & validation

1. Backend first; run migrations; exercise `tests/`, `testing/e2e_test_runner.py`, `test_uploads/`.
2. Confirm: `upload/pdf`+`upload/image` return `processing`+`job_id`; `map` returns `processing`; jobs reach `completed`; **no emails until mapping done**; re-upload duplicate file adds no evidence.
3. Frontend: build UI, load unpacked extension; verify login → scan (table + schema+payload posted + intent) → two-endpoint upload → Process & Map (non-blocking) → email after mapping → refresh table → Submit (fill + store).

---

## 8. Implementation order

1. Repo helpers + migration (`report_intents` + `form_schemas.scanned_payload`) + `get_user_email`
2. Intent task + `POST/GET /reports/{id}/form_schema` (+ `trigger_intent`) + `GET /reports/{id}/mapping`
3. `run_mapping` refactor + async `/map` + `map_task` (email on success)
4. Upload dedup / zip-pdf-ignore / per-file status + **remove** pdf/image emails
5. Delta embeddings + Celery registration
6. Frontend: auth → scan/create/form_schema → two-endpoint upload → Process & Map → status refresh → Submit
7. Rebuild UI + end-to-end validation

---

This is the complete, locked plan. Toggle to **Act mode** and I'll begin with step 1 (backend: repo helpers + migration).
