# Production Plan — AI Report Automation

**Date:** 2026-09-02 · **Branch:** `restructuring` · Companion: `AUDIT_REPORT.md` (findings referenced as 🔴/🟠/🟡 #n)

Guiding decisions:

1. **Keep the backend architecture as-is.** `app.py` composition root → `features/` (routes/service/repo) → `ai/` capability layer with the import rule `features → ai` (never reverse), DI container, domain-manifest data-driven design. Do not rebuild — fix and harden.
2. **The frontend is where the rebuild is.** The recurring bug pattern is hand-synced contracts across three layers (UI ↔ background ↔ backend). Rebuild strategy: **one generated contract, one state owner, one adapter system.**
3. **Production posture:** the API is stateless; everything else is a managed service or a container with a real health contract.

## Part 1 — Backend: small fixes, then harden

### 1.1 Fix list (priority order)

| # | Fix | Where | Audit ref |
|---|-----|-------|-----------|
| 1 | Compose/Dockerfile: `backend.app:app`, `celery -A backend.celery_app`, `PYTHONPATH=/app` | `docker-compose.yml`, `Dockerfile` | 🔴 #1 |
| 2 | Exception handlers: `return JSONResponse(...)` instead of `raise HTTPException`; raise `NotFoundError/ConflictError/...` in repositories; drop direct `HTTPException` from services | `app.py`, `features/*` | 🟠 #4 |
| 3 | Duplicate register → 409 via `ConflictError` | `auth/routes.py` | 🟠 #5 |
| 4 | Healthcheck `start_period: 240s` + lazy ML loading (import torch/docling inside extractors, not at boot) — kills the ~4-min cold start | `container.py`, `ai/extraction/*` | 🟡 #9 |
| 5 | Worker liveness signal: `/ready` reports broker reachability + worker heartbeat; job status distinguishes `queued` from `worker_offline` | `app.py`, `tasks/` | 🔴 #2 |
| 6 | Fail hard on `JWT_SECRET_KEY=default` when `ENV=production`; explicit CORS origins, never `*` | `core/config.py`, `app.py` | 🟡 #14 |
| 7 | `/map` with unknown domain name → 400 "Unknown domain", not silent `domain_id=None` | `reports/routes.py:840-850` | 🟠 #6 |
| 8 | Idempotent auto-seed of domains/manifests at startup (keep seed script as explicit CLI) | `domain_catalog/loader.py` | 🟠 #6 |

### 1.2 Production hardening (verified gaps)

- **Rate limiting to Redis** — the in-memory login limiter (🟠 #8) is per-process. Redis sliding window (Redis already in the stack).
- **Refresh-token rotation + revocation** — store hashed `jti` in Postgres, rotate on `/auth/refresh`, revoke on logout. Today a leaked refresh token is valid 7 days unconditionally.
- **File validation at the boundary** — fake PDFs are accepted and enqueued (fail later in Docling). Validate magic bytes (`%PDF-`, PNG/JPEG headers), cap size at the ASGI layer, reject before job creation.
- **Alembic only in production.** API container runs `alembic upgrade head`; `create_all` behind `ENV=dev`.
- **Structured logging** — JSON logs with `request_id` middleware, propagated into Celery task logs.
- **Stuck-state sweeper** — `mapping_in_progress=True` survives worker crashes. Celery beat: jobs/flags older than N minutes without heartbeat → mark `failed`, release lock.
- **Job row = source of truth.** Postgres job rows carry the state machine (`queued → running → completed/failed`); Redis is broker only. Worker death becomes observable.


### 1.3 Deployment shape

```
                     ┌── nginx/ALB (TLS, body-size limits, /health passthrough)
                     │
   FastAPI (2+ replicas, uvicorn workers=2, --limit-concurrency)
   Celery worker (pdf / image / intent queues split; autoscale on queue depth)
   Celery beat (stale-job sweeper, lock reaper, token cleanup)
                     │
   Postgres 16 (managed; pgbouncer; replace NullPool with a real pool)
   Redis (broker + cache + rate limit; AOF on)
   Qdrant (managed, or single node + snapshot volume)
   S3-compatible storage ← uploads/processed files (replaces ./storage volume)
```

Two changes matter most: **S3 for file storage** (`storage/` and `uploads/` are container-local volumes — replicas can't share them; restarts lose in-flight files) and **splitting Celery queues** so one large PDF doesn't block intent jobs.

## Part 2 — Frontend/Extension: rebuild the shell, keep the features

The feature components (DocumentsSection, Drawer, FormFieldsTable, ReportsSection) are fine. The plumbing underneath gets rebuilt.

### 2.1 Contract-first (keystone)

```
FastAPI /openapi.json
   └── openapi-typescript → src/lib/api/schema.d.ts   (types, committed)
   └── openapi-fetch      → src/lib/api/client.ts     (typed fetch client)
```

- One typed client used by background worker AND standalone mode.
- Hand-synced drift bugs (`/auth/token` JSON vs form, `/unlock` body, missing `/status`, `domain_id` vs `domain`, `/domains/` trailing slash) become compile errors.
- CI step: regenerate + `git diff --exit-code` so backend changes that break the frontend fail the build.

### 2.2 One state owner

- Background owns ALL server state (auth, reports, documents, schema, mappings, lock).
- UI connects via `chrome.runtime.connect()` Port: full snapshot on connect, patches afterwards (`{type:"documents", value}`, `{type:"lock", ...}`).
- Zustand becomes a thin reducer of patches, validated with zod (types derived from OpenAPI).
- Structurally deletes the `getState().data` bug, the `USER_EMAIL` undefined-key bug, and the never-rendered lock banner.

### 2.3 Fix the topology

- `frontend/web` builds **directly into `extension/ui/dist`**; delete the `frontend/openquire-ai-extension` ghost copy (🟡 #12 wiring).
- Standalone mode: recommend **delete** (half-implemented: localStorage token never set, invented `reportId` via `crypto.randomUUID()`); otherwise implement login + report creation behind the same typed client.
- Delete `platformAdapter.ts` / `openquireAdapter.ts` (proven dead — always return `{}`). Platform knowledge lives ONLY in `extension/adapters/*.adapter.json` per the stated design principle.

### 2.4 Real review UX

Mapping drawer = actual human gate: editable values, confidence badges, per-field accept/reject, then "Apply to form". `mappingApproved` means a human approved these specific values; auto-fill sends only accepted fields. Remove the auto-approve-on-generate path.

### 2.5 Server-authored documents

- Upload response's server `document_id` becomes the store's ID (no local UUIDs).
- Delete → `DELETE /reports/{id}/documents/{document_id}` with the lock token.
- After any mutation, background re-fetches `GET /reports/{id}` and pushes the snapshot.

## Part 3 — Cross-cutting production requirements

### 3.1 Observability

- JSON logs + `request_id` (API → Celery → Modal calls): one trace ID across the pipeline.
- Sentry (backend + extension background).
- Metrics: queue depth, extraction duration per doc type, mapping success rate, LLM token spend (`utils/token_tracker.py` → export to Prometheus instead of logs).
- Alerts: queue age > 5 min, worker heartbeat missing, `/ready` degraded, LLM error rate.

### 3.2 Security

- TLS everywhere; extension `host_permissions` narrowed to the deployed API domain (remove `localhost:8000` in prod builds).
- Secrets via Vault/SSM, never `.env` in images; rotate the `QODER_PAT` present in the working tree (🟡 #13).
- Verify Qdrant payloads carry `user_id`/`report_id` filters — report scoping exists in Postgres; shared vector collections without payload filters are the classic leak.

### 3.3 CI/CD

```
lint → typecheck (frontend) → pytest (backend, tests/ suite) →
openapi-diff check → build extension → docker build →
deploy staging → tests/smoke_api.py against staging → deploy prod
```

`tests/smoke_api.py` becomes the deployment gate verbatim.

### 3.4 Scaling path (in order of actual need)

1. Celery queue split + concurrency tuning (extraction is the bottleneck; Modal already scales that out).
2. Multiple uvicorn replicas behind nginx (stateless already, except `storage/` → S3).
3. Qdrant snapshots + collection-per-domain as manifests grow.
4. Postgres read replica only when report-list queries slow down (not soon).

## Week-one execution checklist (mechanical, low-risk, smoke-tested after each)

1. Compose/Dockerfile entrypoints + `PYTHONPATH` (unblocks everything; ~30 min) — 🔴 #1
2. Exception handlers → return responses + `ConflictError` usage (~1 hr) — 🟠 #4/#5
3. vite `outDir` → `extension/ui/dist`, rebuild (~15 min)
4. `getState().data` fix + `USER_EMAIL` key + lock banner wiring (~2 hrs)
5. Domain auto-seed + `/map` unknown-domain 400 (~1 hr) — 🟠 #6
6. `deleteDocument` → real backend endpoint with real IDs (~1 hr)
7. Wire `tests/smoke_api.py` into CI

Next sprint: contract generation (2.1) + single state owner (2.2). Sprint after: backend hardening (S3, refresh tokens, Redis rate limits, job sweeper).

Run `tests/smoke_api.py` after every backend change to prove no regressions.

