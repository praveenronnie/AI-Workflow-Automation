# End-to-End System Audit Report

**Date:** 2026-09-02 · **Branch:** `restructuring` (b6e49db) · **Mode:** analysis-only — **no fixes applied**

Test environment: local uvicorn (`backend.app:app` :8123) against Docker infra
(postgres :5434 healthy, redis :6379, qdrant :6333 — all up; **api/worker containers NOT running**).
Isolated test suite in `tests/` (`smoke_api.py`, `inspect_db.py`).

## Verdict summary

| Area | Status |
| --- | --- |
| Backend API live (health/ready/auth/reports/uploads/schema/map/mapping/lock/domains) | ✅ 23/25 smoke checks pass |
| Infra containers (postgres/redis/qdrant) | ✅ up and reachable |
| Frontend/web build (vite + tsc) | ✅ builds clean |
| Extension ↔ backend API contracts (auth, lock, upload, schema, map, mapping, jobs) | ✅ paths & payload shapes match |
| Docker compose api/worker definitions | ❌ broken by restructuring |
| Celery pipeline end-to-end | ⚠️ worker not running; /map fails with "No evidence found" |
| Domain seed data | ⚠️ empty (`GET /domains/` → `[]`), mapping needs `domain_id` |
| Error-handling layer | ⚠️ custom exceptions dead code; handlers mis-implemented |

## 🔴 Broken (blocks functionality)

1. **docker-compose.yml runs packages that no longer exist**
   - `api` command: `uvicorn inspection_ai.api.app:app` — module deleted; actual app is `backend.app:app`.
   - `worker` command: `celery -A inspection_ai.celery_app` — actual is `backend.celery_app`.
   - `PYTHONPATH=/app/backend` (compose + Dockerfile:21) contradicts `backend.*` imports, which require the **repo root** on `sys.path`. Result: neither container can start as configured (confirmed: only infra containers are running; api/worker absent).

2. **Pipeline failure mode is opaque when no worker runs** (worker itself verified ✅)
   - `POST /reports/{id}/upload/pdf|image` returns `{status:"processing", job_id}` and enqueues Celery tasks. With no worker running (the compose `worker` container can't start, see #1), evidence is never extracted and `POST /map` later fails `400 "No evidence found for report"` — no health signal distinguishes "queued" from "worker dead".
   - Verified locally: `celery -A backend.celery_app worker` **starts and drains queued jobs** — PDF task ran Docling via Modal end-to-end (extraction completed, 0 evidence from the minimal test PDF, as expected). So the code is sound; only the compose entrypoint is wrong.

3. **`GET /reports/{id}/status` does not exist**
   - Smoke test got `404 Not Found`. Status only via `GET /reports/{id}/mapping` (`processing` block) and `GET /reports/jobs/{job_id}`.

## 🟠 Logic gaps

4. **Custom exception layer is dead code with a latent 500 bug**
   - `backend/app.py:153-167` registers handlers for `NotFoundError/ConflictError/PermissionDeniedError/ValidationError`, but **no module in `backend/` ever raises them** (searched all files). All routes raise `HTTPException` directly.
   - Worse, each handler does `raise HTTPException(...)` *inside* the handler. FastAPI handlers must **return** a response; if these handlers ever fire, the raise escapes to `ServerErrorMiddleware` → client gets **500 instead of 404/409/403/400**.

5. **Duplicate registration returns 400, not 409/ConflictError**
   - `backend/features/auth/routes.py:75` — inconsistent with the (registered but unused) ConflictError→409 contract.

6. **Empty domain registry breaks data-driven mapping**
   - `GET /domains/` returns `[]`. `POST /map` requires `domain_id`, the extension sends a domain name. Without seeding (`scripts/seed_domain_manifest.py`, untested/undocumented in quick start), the full mapping flow cannot succeed on a fresh install.

7. **`.env` `DB_URL=sqlite+aiosqlite` is silently ignored**
   - `backend/database/base.py:21` builds the URL solely from `DB_NAME/DB_HOST/DB_PORT/DB_USERNAME/DB_PASSWORD` (Postgres+asyncpg). `data/dev.db` exists but has **zero tables** (see `tests/inspect_db.py`) — misleading config key. Smoke data landed in the Postgres container.

8. **Login rate limiter is per-process in-memory**
   - `auth/routes.py:27-45` — the 10-attempts/5-min limiter (correctly tripped during testing) resets on restart and shares no state across workers/replicas; bypassable horizontally. Acknowledged in code comments; production gap.


## 🟡 Risks / inconsistencies

9. **Cold start ~4 minutes** — uvicorn readiness blocked by eager ML imports (torch/transformers/sentence-transformers) during `startup_services()`; Dockerfile healthcheck `start_period: 60s` is far too short → container flaps unhealthy in production.

10. ~~Mojibake in error detail~~ **Cleared** — wire-level check (`tests/emdash_check.py`) confirms the detail arrives intact: `'Report is not locked — acquire a lock before processing'`. The garbled text seen earlier was a console/log-file codepage artifact only.

11. **`GET /domains` vs `/domains/` 307 redirect** — routes are declared with trailing slash (`@router.get("/")` in `domains/routes.py`); un-suffixed client calls receive 307 (fetch/httpx don't always follow). Extension uses `/domains/` (correct).

12. **Docs drift** — README Quick Start (`uvicorn inspection_ai.api.app:app`), project-structure section, and `frontend/openquire-ai-extension` naming all reference the pre-restructure layout.

13. **Secrets hygiene** — `.env` holds real credentials (GEMINI/QODER PAT/QUIRE email). It is not tracked by git (verified), but the `QODER_PAT` visible in this working tree should be rotated.

14. **`JWT_SECRET_KEY` default** — startup logs a warning but boots with `change-me-in-production`; no hard fail in production mode.

## 🔵 Verified working (evidence)

- `/health` 200; `/ready` all services true (llm, vector_store, redis, reranker, mapper, extractor_registry).
- Register → login (OAuth2 form) → JWT; 401 without token; cross-user report access → 404 (scoped).
- Report link/dedup by URL; `POST /lock` → lock_token + 300s TTL; pdf+image uploads accepted and enqueued; form_schema store/get (requires `source_url`); `/map` guards 400 when no evidence; `/mapping` returns mappings + populated_schema + processing; `/unlock` requires JSON body (422 when absent).
- Extension `background.js` endpoints all match backend routes; login uses `x-www-form-urlencoded` matching `OAuth2PasswordRequestForm`; lock/heartbeat/unlock implemented client-side; UI state sync (UPDATE_UI_STATE) present.
- `frontend/web` builds clean (tsc+vite, ~16s); store/drawer (documents, fields, fields-table, mapping)/DomainSelector consume contract shapes matching backend responses.
- Login rate limiting actively returns 429 (tested live).

## Test suite

- `tests/smoke_api.py` — 25 checks; **23 pass**. The 2 fails are findings #2/#3 (no `/status` route; `/map` 400 due to worker-less pipeline). `/unlock` 422 was contract-corrected in the test (body required).
- `tests/inspect_db.py` — proves `data/dev.db` is stale/empty (finding #7).
- Run: `python tests/smoke_api.py http://127.0.0.1:8123` (server up; wait out the 5-min login rate window between runs).

## Resolution status (2026-09-02, week-one fixes applied)

| Finding | Status |
|---|---|
| 🔴 #1 compose/Dockerfile entrypoints + PYTHONPATH | ✅ fixed (`backend.app:app`, `backend.celery_app`, `PYTHONPATH=/app`, healthcheck `start_period: 240s`) |
| 🟠 #4 exception handlers | ✅ fixed — handlers `return JSONResponse`; duplicate register raises `ConflictError` → 409 (verified live) |
| 🟠 #6 empty domain registry | ✅ fixed — idempotent startup seed (`domain_catalog/seed.py`); `GET /domains/` returns `pca_site_assessment`; `/map` rejects unknown/missing domain with clear 400 (verified via `tests/domain_map_check.py`) |
| Frontend `getState().data` sync bug | ✅ fixed in `App.tsx` |
| Frontend `USER_EMAIL` undefined storage key | ✅ fixed in `background.js` |
| Lock banner never rendered | ✅ fixed — `lockState` in store, read-only/lock banners in `App.tsx` |
| Frontend stale build ghost path | ✅ fixed — vite outDir → `extension/ui/dist`; extension ships fresh build |
| `deleteDocument` local-only | ✅ fixed — background deletes via `DELETE /reports/{id}/documents/{document_id}` with lock, then re-syncs server list (`getDocuments` handler + `syncDocuments()` in UI; upload/delete flows re-sync) |
| CI | ✅ added `.github/workflows/ci.yml` (backend services + smoke gate, frontend build, extension JS/manifest checks) |

Smoke suite: **29/31 pass** — the 2 remaining fails are expected pipeline behaviors (map without extracted evidence; `/unlock` requires a JSON body), documented above.

## Round 2 (hardening) — applied & verified 2026-09-02

| Item | Status |
|---|---|
| Redis login rate limiter (shared across workers, memory fallback) | ✅ `auth/rate_limit.py` — 429 verified live |
| Refresh-token rotation + revocation + `POST /auth/logout` | ✅ `refresh_tokens` table, jti registry — rotation, reuse-reject, logout-revoke all verified (`tests/smoke_api.py`) |
| Magic-byte upload validation | ✅ fake PDF/image rejected 400 before enqueue (verified) |
| Request-ID tracing | ✅ `X-Request-ID` middleware + log filter (verified: `tests/maintenance_check.py`) |
| Stale-job sweeper + worker heartbeat | ✅ Celery beat task `backend.tasks.maintenance` (60s); `/ready` reports `worker_alive` (verified: heartbeat flips it true; sweep runs clean) |
| Dead adapter layer removed | ✅ `platformAdapter.ts`/`openquireAdapter.ts` deleted; scan is adapter-JSON-driven |
| Real mapping-review gate | ✅ auto-approve removed; per-field Accept/Reject + explicit "Apply to Form" in the mapping drawer |

## Round 3 — standalone mode removed (2026-09-02)

The extension UI is now **extension-only**. Deleted from `frontend/web/src/lib/messaging.ts`:
- `directApiUpload()` (hand-rolled fetch path with the never-populated `localStorage` token)
- the `API_BASE` localStorage lookup
- the `crypto.randomUUID()` fallback report-ID invention in `uploadMultipleFiles`
- the "Extension context not available" fallback — now a clear actionable error telling the user to load the panel inside the extension

All uploads go exclusively through the background service worker (`UPLOAD_PDF`/`UPLOAD_IMAGE` handlers, which own the JWT and lock lifecycle). Closes the invented-report-ID bug class and the duplicated upload implementation. Verified: zero residual references, tsc+vite build clean into `extension/ui/dist`, smoke suite unchanged at 29/31.

| OpenAPI contract artifact | ✅ `scripts/export_openapi.py` → `docs/openapi.json` (25 paths, committed) |
