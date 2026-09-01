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
Chrome Extension (MV3)
├── Side Panel UI (ui/ — React + Zustand)
├── Background Service Worker (all backend API calls, JWT)
└── Content Script (DOM + adapter registry)
      └── adapters/*.adapter.json  → declarative platform config
          extraction strategies (api + dom), fillers, parsers
                │ REST + JWT
                v
FastAPI (inspection_ai/api)
├── /auth (JWT)  /reports (upload, schema, map)  /domains (manifests, prompts)
└── universal_service/  ← core (platform & domain agnostic)
      ├── extractors/  pdf (Docling/Modal) · handwritten (VLM) · image · zip
      ├── indexer/     Qdrant vectors + BM25 + cross-encoder reranker
      ├── mapper/      alias → retrieval → rule → LLM, concurrent per section
      └── storage/     evidence store · report registry · Redis cache

Celery worker: pdf/image/intent/embed tasks
Infra: PostgreSQL · Redis · Qdrant · Modal (GPU inference)
```

## Project Structure

```
ai-report-automation/
├── inspection_ai/
│   ├── api/                  # FastAPI app, auth, report & domain routes
│   ├── database/             # SQLAlchemy models + repositories (Postgres)
│   ├── universal_service/    # CORE: extraction, indexing, mapping (agnostic)
│   ├── services/             # LLM client, Docling, intent detection, Modal executor
│   ├── tasks/                # Celery tasks (pdf, image, embed, intent)
│   ├── worker/               # Modal app definitions (docling, embeddings)
│   └── config.py             # Pydantic settings (.env)
├── openquire-ai-extension/   # Chrome extension
│   ├── adapters/             # Declarative platform adapter configs (+ index.json)
│   ├── content/              # Scanner, fillers, adapter registry, extractors
│   ├── background/           # Service worker (backend API + state)
│   ├── domains/manifests/    # Domain manifest JSONs
│   └── shared/               # Constants + schemas
├── ui/                       # Side panel (React + TS + Vite)
├── scripts/                  # Domain manifest seeding / payload generation
├── testing/                  # Manual test fixtures (JSON results)
└── docker-compose.yml        # Redis, Qdrant, Postgres, Celery worker
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
