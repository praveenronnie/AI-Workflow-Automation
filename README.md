# FormIQ

**Intelligent filling for inspection reports.** A Chrome extension + FastAPI
backend that captures any web form, matches your uploaded documents to its
fields with confidence scores, and fills it after human review.

> formerly "OpenQuire AI Form Automation" / FormPilot concept

## Architecture

```
Chrome Extension (extension/)
├── Side panel UI (frontend/web → builds to extension/ui/dist)
├── Background service worker — ALL backend API calls, JWT, report locks
└── Content scripts — DOM scanner, capture mode, generic fillers
      │ REST + JWT
      v
FastAPI backend (backend/, package root — run as backend.app:app)
├── app.py            composition root (lifespan, routers, exception handlers)
├── features/         auth · reports · domains · mapping (routes → service → repo)
├── workflows/        cross-feature orchestration
├── ai/               extraction (Docling/Modal, VLM) · retrieval (Qdrant+BM25) · mapping
├── core/             config, logging (request-ID), DI container, exceptions
├── database/         SQLAlchemy models (Postgres) + repositories
├── tasks/ worker/    Celery worker · beat (heartbeat + stale-job sweeper) · Modal
└── domain_catalog/   domain manifests (auto-seeded at startup)

Infra: PostgreSQL · Redis · Qdrant · Modal (GPU inference) · OmniRoute (LLM gateway, docker service)
```

**Privacy model:** documents/evidence are deduplicated and shared **within an
organization**; every lookup, dedup index, and vector-search filter is
org-scoped. Cross-org access returns 404 by design.

## Quick start (dev)

```bash
# 1. Infrastructure
docker compose up -d postgres redis qdrant

# 2. Backend (repo root on PYTHONPATH — imports are backend.*)
pip install -r requirements.txt
python -m uvicorn backend.app:app --reload --port 8000

# 3. Frontend → extension bundle
cd frontend/web && npm install && npm run build   # outputs ../extension/ui/dist

# 4. Chrome: chrome://extensions → Developer mode → Load unpacked → extension/
```

Configuration lives in `.env` — only keys actually read by the code (see
comments in `.env`). Generate the JWT secret with
`python -c "import secrets; print(secrets.token_urlsafe(48))"`.

## API overview

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET    | /health · /ready | liveness · readiness (services + worker heartbeat) |
| POST   | /auth/register · /auth/token · /auth/refresh · /auth/logout | JWT with refresh rotation + revocation |
| POST   | /reports/link | create-or-link report by URL (org-scoped) |
| POST   | /reports/{id}/lock · /lock/heartbeat · /unlock | report locks (300s TTL) |
| POST   | /reports/{id}/upload/pdf · /upload/image | uploads (magic-byte validated, org-scoped dedup, Celery) |
| POST/GET/PUT | /reports/{id}/form_schema | scanned/consolidated form schema |
| POST   | /reports/{id}/map | alias → retrieval → rule → LLM mapping (domain required) |
| GET    | /reports/{id}/mapping · /reports/{id}/documents… | results, status |
| GET/POST | /domains/ · /domains/upload · /domains/{id}/manifests | domain registry (auto-seeded) |

OpenAPI contract: `docs/openapi.json` (regenerate: `python scripts/export_openapi.py`).

## Testing

```bash
python testing/runner.py http://localhost:8000   # FULL battery (14 suites, incl. E2E)
python tests/smoke_api.py http://localhost:8000   # 31-check API gate
python tests/org_isolation_check.py               # privacy walls
python tests/domain_map_check.py                  # domain validation
python tests/maintenance_check.py                 # heartbeat/sweeper
```

`testing/runner.py` is the deployment gate — it runs every suite in dependency
order and prints a pass/fail summary (`testing/TEST_CASES.md` maps ~120 cases
to suites). `tests/pipeline_check.py` inside it needs a live worker + Modal.

## Production

See `docs/PRODUCTION_PLAN.md` (rollout plan) and `docs/AUDIT_REPORT.md` (audit
trail + resolution status); `docs/PROJECT_STATUS.md` tracks phase status.
Deployment shape: `docker-compose.prod.yml` + `Caddyfile` (TLS via Caddy) with
OmniRoute as an in-network LLM gateway (never `localhost` — the API refuses to
boot with `ENV=production` and a loopback URL). Release/troubleshooting runbook:
`docs/DEPLOYMENT.md`.
