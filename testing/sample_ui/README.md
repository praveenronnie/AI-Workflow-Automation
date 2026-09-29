# FormIQ Sample UI Test Harness

A self-contained, **no-build-step** browser harness that replicates the OpenQuire PCA
form from `form_schema.json` and drives the **real FastAPI backend** end-to-end. It
replaces both the Chrome extension and the live website for complete testing of the
core pipeline:

1. **Document uploading** — real `POST /upload/pdf` + `POST /upload/image`, dedup, job tracking
2. **Mapping** — real `POST /map` (alias → retrieval → rule → LLM)
3. **Human verifying with tables** — editable review tables with accept/reject + confidence
4. **Submitting (populating in webpage)** — real DOM fill of the rendered form via events

The harness only renders the fields that exist in the schema — the 35 `tables` entries
with one or more fields.

## Files

| File | Purpose |
|------|---------|
| `index.html`  | Single-page wizard UI (6 steps) + API log panel |
| `app.js`      | All logic: API client, form renderer, upload, map, review, fill |
| `styles.css`  | Minimal dark styling |
| `form_schema.json` | Copy of `data/form_schema.json` (loaded locally, POSTed to backend) |

## Run it

**0. Prerequisites (start the real backend first):**

```bash
docker compose up -d postgres redis qdrant
python -m uvicorn backend.app:app --reload --port 8000
```

Also make sure the LLM proxy in `.env` is reachable (the map step needs it). A Celery
worker is *optional* — the backend falls back to inline processing when Redis/broker
isn't running, but job polling still works either way.

**1. Serve the sample UI** (needs a static file server; CORS already allows `:5173`):

```bash
cd testing/sample_ui
python -m http.server 5173
# open http://localhost:5173
```

> If you use a different port, add it to `CORS_ALLOW_ORIGINS` in `.env` and restart the
> backend. No other config changes are required.

## The 6 steps

| Step | What it does | Backend calls |
|------|--------------|---------------|
| **0 Connect** | Set backend URL, check `/health` + `/ready`, auto-register + login a random test user | GET `/health`, `/ready`, POST `/auth/register`, `/auth/token`, GET `/domains/` |
| **1 Report & Form** | Link report for a local URL, acquire lock (auto heartbeat 60s), load + render schema, POST it | POST `/reports/link`, `/reports/{id}/lock`, POST `/reports/{id}/form_schema` |
| **2 Upload** | Pick files; PDFs → upload/pdf (with doc-type), images/ZIP → upload/image; polls jobs | POST `/upload/pdf`, `/upload/image`, GET `/reports/jobs/{job_id}` |
| **3 Map** | Pick domain, call the real map endpoint, show summary | POST `/reports/{id}/map` |
| **4 Verify** | Table-by-table review: editable value, confidence, source, ✓/✗; accept-all / clear | (in-memory only) |
| **5 Submit** | Fill accepted values into the rendered form (DOM events), highlight filled fields | (in-memory only) |

## Suggested test data

- **PDF:** `data/MarketSTPCA.pdf` (rich OCR text for mapping) — try both *Scanned* and
  *Handwritten* doc types.
- **Images:** any `data/site_images/*.jpg` for the image/VLM path.
- **Dedup:** upload the same file twice — second time should report the knowledge-base
  "linked" path instead of re-extracting.

## What's logged

Every API call (method, path, status, truncated body) streams into the right-hand
**API Log** panel — useful to confirm request/response contracts and spot errors.

## Testing checklist (E2E)

- [ ] Health + ready OK; user registered/token acquired
- [ ] Report linked (dedup works for same URL), lock acquired, heartbeat alive
- [ ] Form replica renders only tables with fields; schema POST returns `stored`
- [ ] PDF upload → `processing`/job_id → job reaches `completed`
- [ ] Image upload accepted; fake/oversized files rejected with 400
- [ ] Duplicate upload returns the "linked" dedup path (no re-extraction)
- [ ] Map returns mappings + populated_schema; unmatched fields shown
- [ ] Review table shows confidence + source; edit value, accept/reject works
- [ ] Submit fills the page; filled fields highlighted; fill summary accurate
- [ ] `GET /reports/{id}/mapping` (via API) includes the same persisted mappings

## Notes / limitations

- Decisions and filled values are kept **in-memory** only (same model as the extension —
  no new backend endpoints are added).
- The harness auto-creates a fresh random test user on Connect. Use **New test user**
  to reset auth without reloading.
- `AbortSignal.timeout` is used; older browsers may need a fresh browser or a fallback.
- This is a *test rig*, not the production UI — keep the two separate.