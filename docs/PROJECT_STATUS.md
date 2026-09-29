# FormIQ — Project Status

**Updated:** 2026-09-04 · Branch `restructuring` · **Docker deployment: LIVE & TESTED** (api + worker + beat-less dev stack on localhost:8000)
Companion docs: `PRODUCTION_PLAN.md`, `AUDIT_REPORT.md`

Legend: ✅ DONE (implemented + verified) · 🟡 READY (code/spec complete, blocked on your input) · ⏳ PENDING (not started)

## 🚀 Docker deployment verification (latest)
| Check | Result |
|---|---|
| `docker compose up -d` — api + worker containers run with fixed entrypoints | ✅ first time ever |
| `/ready` in container: llm, vector_store, redis (after `REDIS_HOST: redis` fix), reranker, mapper, extractor_registry | ✅ all true |
| Full pipeline E2E in Docker (`tests/pipeline_check.py`): upload → Celery worker → Modal Docling → evidence + embeddings → form_schema → /map → **3/3 fields mapped with correct values** ("Foundation Type → Slab", 98%) | ✅ 0 fails |
| Smoke suite vs Docker api | ✅ 29/31 |
| Org isolation vs Docker api | ✅ 3/3 |
| Domain validation vs Docker api | ✅ |
| **Bugs found & fixed during Docker testing:** Modal auth missing in containers (`MODAL_TOKEN_ID/SECRET` wired into compose + `.env`) · `RegisterResponse.name=None` → 500 (now `str \| None`) · mapping results dropped for `field_id`/`field_name`-keyed schemas (adapter + `build_results` key-chain fixes) · api container Redis connection (`REDIS_HOST: redis`) · dev-compose dead `MODAL_PROXY_*` vars replaced with real Modal creds | ✅ |

## 🧪 Complete test suite (latest — `testing/`)
| Check | Result |
|---|---|
| Test-case spec: `testing/TEST_CASES.md` — ~120 cases, 13 modules + traceability matrix | ✅ |
| Automation: `testing/` — 14 suites via `runner.py` (smoke, auth, lock, schema, domain, docs, ops, org-isolation, domain-map, maintenance, upload-edge, map-flag, concurrency, full-pipeline) | ✅ **14/14 PASS** vs live Docker |
| Bugs surfaced & fixed by the suite: unlock wrong-token 200→403 · delete File-id↔Document-id bridge · concurrent same-content upload race (`IntegrityError`/`MissingGreenlet` → per-content lock) | ✅ |
| Remaining manual: TC-UI extension flows (9, browser checklist in TEST_CASES.md §15) · cold-start timing (NFR-001) · Modal-internal failure paths (N/A by design) | 👁 documented |


## Phase 0 — Trust & privacy walls
| Item | Status |
|---|---|
| Org-scoped document dedup (`documents.org_id`, unique `(org_id, content_hash)` partial index) | ✅ |
| Hash lookups org-filtered in PDF + image upload paths; create stores org | ✅ |
| Legacy global hash index dropped (dev guard in `init_db`; Alembic migration for prod) | ✅ |
| Qdrant fail-closed: unscoped vector searches refused (`search`/`search_batch`); `org_id` filter support | ✅ |
| Cross-org leak test (`tests/org_isolation_check.py`) | ✅ 3/3 — same file in two orgs = two documents, zero linkage |
| Qdrant `org_id` payload written at embed time | ⏳ PENDING (retrieval already fail-closed + document_ids-scoped; payload tagging when embed path is next touched) |

## Phase 1 — Rebrand, design system, workspace
| Item | Status |
|---|---|
| Product renamed **FormIQ** (manifest, panel header, README) | ✅ |
| Professional palette (indigo brand + slate neutrals + success/warning/info tokens, light + dark, `prefers-color-scheme`) | ✅ `frontend/web/src/index.css` |
| New icon artwork (FP/FQ monogram SVG) | ⏳ PENDING (cosmetic; current icon still works) |
| Web Store / domain availability check for "FormIQ" | 🟡 YOUR ACTION |
| Workspace Reports view + [New Report] button | ✅ `WorkspaceView` — report cards, status badges, create/logout (Phase 1) |
| Multi-view panel shell (workspace ⇄ report detail) | ✅ view router in `App.tsx` + `useStore` |
| Binding rule (`claim_url`: manual report adopts first scanned URL) | ✅ via createReport(active tab URL); adopted on scan (existing `storeFormSchema` sourceUrl) |
| Pipeline strip, per-document status, microcopy | ✅ `PipelineStrip` — Upload→Extract→Embed→Map stages, polls report status while processing (Phase 2) |
| Review & Apply screen | ✅ `ReviewScreen` — editable values, option dropdowns, ≥80% auto-accept grouping, preview-before-fill, per-field accept/reject (Phase 3) |
| Page-anchored copilot (chips, two-way sync, dock) | ⏳ PENDING (Phase 4) |
| Form Capture Mode + adapter demotion | ⏳ PENDING (Phase 5) |

## Phase 2 — Pipeline UX
✅ DONE — `PipelineStrip` (Upload→Extract→Embed→Map stages, report-status polling, microcopy) in the report detail view.

## Phase 3 — Review & Apply
✅ DONE (reworked) — `ReviewScreen` renders **one table per section, side by side** (flex-wrap): Field | editable Value | Conf | Src | accept/reject. Edits highlight the row; unmapped inputs say "Not found in documents"; per-section header shows `n/m ready`; sticky Preview/Apply bar; ≥80% auto-accept retained; preview-before-fill modal.

## Phase 4 — Page-anchored copilot (chips, two-way sync, dock)
⏸️ DEFERRED BY DECISION — the section-table Review view (complete scanned/mapped fields per section, editable values, confidence + source columns) covers the need; chips would duplicate it as noise. Revisit only if users ask for in-page navigation.
## Phase 5 — Form Capture Mode + adapter demotion | ⏳ PENDING (design finalized)

## Phase 6 — Cloudflare R2
| Item | Status |
|---|---|
| Credentials in `.env` (`R2_*`, normalized from your Cloudflare keys) | ✅ |
| Storage adapter + initiate/complete presigned flow + worker hash-verify + deletion transaction | 🟡 READY (spec finalized; blocked only on implementing against live bucket) |
| Bucket CORS policy for extension PUTs | 🟡 YOUR ACTION (JSON provided in plan discussion) |

## Phase 7 — Production
| Item | Status |
|---|---|
| `docker-compose.prod.yml` (baked images, Caddy TLS, beat service, log limits, no public Postgres) + `Caddyfile` | ✅ |
| Alembic migration `0001_formiq_privacy` (org_id + index swap + refresh_tokens) | ✅ |
| Clean `.env` (33 → 40 lines, only code-read keys; JWT secret generated; dead credentials removed) | ✅ |
| README rewritten for FormIQ/real architecture | ✅ |
| CI: backend (services + smoke gate) · frontend (OpenAPI typed-client gen + build) · extension checks | ✅ `.github/workflows/ci.yml` |
| OpenAPI contract artifact (`docs/openapi.json`, 25 paths) | ✅ |
| Hetzner deploy (account, DNS, TLS, backups cron) | 🟡 YOUR ACTION (checklist in chat; compose ready) |
| Chrome Web Store packaging (host_permissions → prod domain) | 🟡 after hosting |

## Earlier rounds (already shipped & verified)
- Restructure fixes: compose/Dockerfile entrypoints, `PYTHONPATH=/app` ✅
- **UI build-path fix**: `vite.config.ts` outDir was `../extension/ui/dist` (resolved to a ghost `frontend/extension/` folder) so the extension kept loading the OLD bundle — corrected to `../../extension/ui/dist`; ghost folder deleted; dist now carries the new UI (291KB `index-Bz_bOWSE.js`, verified strings: FormIQ/New Report/Apply to Form/View source) ✅
- Exception handlers return responses; 409 conflicts ✅
- Domain auto-seed + unknown-domain 400 ✅
- Auth: Redis rate limiter, refresh rotation/revocation, logout ✅
- Magic-byte upload validation ✅
- Request-ID tracing + JSON-ready logs ✅
- Celery beat: heartbeat + stale-job sweeper; `/ready` reports `worker_alive` ✅
- Frontend: state-sync fix, `USER_EMAIL` key, lock banners, real review gate, standalone mode removed, vite outDir → `extension/ui/dist`, dead adapters deleted ✅

## Test suite (current, all live)
| Suite | Result |
|---|---|
| `tests/smoke_api.py` | 29/31 (2 fails = documented expected behaviors) |
| `tests/org_isolation_check.py` | 3/3 ✅ |
| `tests/domain_map_check.py` | ✅ |
| `tests/maintenance_check.py` | ✅ |
| `tsc + vite` build → `extension/ui/dist` | ✅ |
| `node --check` extension JS | ✅ |

## Your pending actions
1. Web Store + domain check on **FormIQ**
2. Fill `<YOUR-EXTENSION-ID>` in `.env` CORS origins
3. Rotate exposed credentials (QODER_PAT, GEMINI key, QUIRE password — now deleted from `.env` but still live)
4. Create Hetzner account (checklist ready) → `docker compose -f docker-compose.prod.yml up -d --build`
5. R2 bucket CORS policy (JSON in plan discussion)
