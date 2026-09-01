# AI Report Automation

## Overview

AI-powered form automation for the OpenQuire TRM platform (PCA Site Assessment
domain), built with a **pluggable platform-adapter + domain-manifest** design
so additional platforms and domains can be added without touching the core.

Two main components:

1. **Python Extraction & Mapping Engine** (`inspection_ai/`) — FastAPI backend
   that processes PDFs/images (Docling via Modal, VLM for handwritten pages),
   indexes extracted evidence (Qdrant + BM25 hybrid retrieval), and maps form
   fields to evidence via alias → rule → LLM pipeline.
2. **Chrome Extension** (`openquire-ai-extension/`) — MV3 extension with a
   React side panel (`ui/`) that scans forms (adapter-driven API + DOM),
   requests mappings, and auto-fills reports.

## Architecture

```
Chrome Extension (extension/)
├── Side Panel UI (React + Zustand)
├── Background Service Worker (all backend API calls, JWT)
└── Content Scripts (scanner, fillers, adapter registry, extractors)
      └── adapters/*.adapter.json  → declarative platform config
                │ REST + JWT
                v
FastAPI backend (backend/inspection_ai — package: inspection_ai)
├── app.py                  composition root (lifespan, routers, exception handlers)
├── features/               business features: reports/documents/mapping/domains/auth
│   └── each owns routes → payloads → service → repository
├── workflows/              cross-feature orchestration (report processing)
├── ai/                     RAG capability layer (domain-agnostic)
│   ├── extraction/         pdf (Docling/Modal) · handwritten (VLM) · image · zip
│   ├── retrieval/          Qdrant vectors + BM25 + cross-encoder reranker
│   ├── mapping/            alias → retrieval → rule → LLM
│   ├── providers/          LLM client, Modal inference, Docling, intent detection
│   └── storage/models/prompts
├── core/                   config, logging, exceptions, DI container, paths, constants
├── database/               ORM models + shared session (repositories inside features)
├── tasks/ worker/          Celery + Modal workers
└── domain_catalog/ prompts/

frontend/web/               React + Vite dashboard (src/features/...)
json_extraction/            extraction output artifacts
migrations/ scripts/ docs/  Alembic, seed tooling, documentation

Infra: PostgreSQL · Redis · Qdrant · Modal (GPU inference)
Celery worker: pdf/image/intent/embed/embed tasks
```

Import rule: `api → features/workflows → ai/database`. The `ai/` package never
imports `features`, `api`, or `tasks` — it stays swappable and testable in
isolation.

## Project Structure

```
ai-report-automation/
├── backend/inspection_ai/
│   ├── app.py                  # FastAPI composition root (lifespan, routers, handlers)
│   ├── core/                   # config, logging, DI container, exceptions, paths, constants
│   ├── features/               # business features (routes, payloads, services, repos)
│   ├── workflows/              # cross-feature orchestration
│   ├── ai/                     # RAG capability layer (extraction, retrieval, mapping, providers)
│   ├── database/               # SQLAlchemy models + shared session (Postgres)
│   ├── tasks/ worker/          # Celery + Modal workers
│   └── domain_catalog/ prompts/
├── frontend/web/               # React + Vite dashboard (src/features/...)
├── extension/                  # Chrome MV3 extension
│   ├── adapters/               # Declarative platform adapter configs (+ index.json)
│   ├── content/                # Scanner, fillers, adapter registry, extractors
│   ├── background/             # Service worker (backend API + state)
│   ├── domains/manifests/      # Domain manifest JSONs
│   └── shared/                 # Constants + schemas
├── json_extraction/            # Extraction output artifacts
├── migrations/ scripts/ docs/  # Alembic, seed tooling, documentation
└── docker-compose.yml          # Redis, Qdrant, Postgres, Celery worker, API
```

## Quick Start

```bash
# 1. Infrastructure
docker compose up -d redis qdrant postgres worker

# 2. Backend
pip install -r requirements.txt
uvicorn inspection_ai.api.app:app --reload --port 8000

# 3. Extension (Chrome)
#    chrome://extensions → Developer mode → Load unpacked → openquire-ai-extension/
```

## API Endpoints

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET    | /health | Health check |
| POST   | /auth/register | Register a user (JWT auth) |
| POST   | /auth/token | Login → access/refresh tokens |
| POST   | /reports | Create a report (user-scoped) |
| POST   | /reports/{id}/upload/pdf | Upload PDFs (`doc_types` = JSON array of `{contains_handwritten: bool}`) |
| POST   | /reports/{id}/upload/image | Upload images or ZIP (bulk) |
| POST   | /reports/{id}/form_schema | Store scanned form schema (optionally triggers intent pre-pass) |
| POST   | /reports/{id}/map | Map extracted evidence to form fields (`domain_id` required) |
| GET    | /reports/user | List the user's reports |
| GET    | /reports/{id}/mapping | Mapping results + processing status |
| GET/POST | /domains, /domains/{id}/manifests, /domains/upload | Domain & manifest CRUD |

## Extending

- **New domain** — upload a manifest via `POST /domains/upload` (sections →
  fields with aliases/intents). No code changes; the mapping pipeline and UI
  domain selector are data-driven.
- **New platform** — add `adapters/<platform>.adapter.json` + an entry in
  `adapters/index.json` + one extractor file registering named handlers
  (e.g. `<platform>.buildSchema`) with `ApiExtractorRegistry`. The content
  script and backend require no changes.

## Design Principles

- **Platform coupling lives only in adapter configs** — the backend and the
  universal service hold no platform-specific logic.
- **Domain knowledge lives in manifests** — sections, fields, aliases, intents.
- **DOM first, API where available** — adapters declare extraction strategies.
- **LLM for mapping only** — retrieval + rules resolve most fields; the LLM is
  the fallback and resolves `option_id`s.

## License

MIT
