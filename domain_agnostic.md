**MVP Plan – “Domain‑agnostic” core with + a single “Site Inspection” domain**

The goal is to let the extension **discover** the current domain from the backend (so the UI can choose a domain instead of hard‑coding), while keeping the present _report_ logic intact and untouched.

Below is the clean, step‑by‑step roadmap that will add the **new API layer** for domains/prompts and wire it into the UI without affecting the existing business logic.

---

## 1. Backend – minimal domain & prompt API

| Piece                  | File/Path                                                            | What it does                                                                                                                                            | Notes                                                                  |
| ---------------------- | -------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| **Data models**        | `api/models/domain.py` `api/models/prompt.py`                        | `Domain` (id, name, description) – single table for all supported domains.<br> `Prompt` (id, domain_id, name, text) – a prompt belongs to one domain.   | **MVP** – no unique constraints beyond FK.                             |
| **Schemas**            | `api/schemas/domain.py` `api/schemas/prompt.py`                      | Pydantic models for request/response.                                                                                                                   |                                                                        |
| **Routers**            | `api/domains_routes.py` `api/prompts_routes.py`                      | <ul><li>`GET /domains` → list domains.</li><li>`POST /domains` → create a new domain.</li><li>`POST /prompts` → create a prompt for a domain.</li></ul> | No pagination, no RBAC – straight CRUD.                                |
| **Mounting**           | `main.py` (or wherever the FastAPI app lives)                        | `app.include_router(domains_routes.router)` `app.include_router(prompts_routes.router)`                                                                 | Belongs to the same `app` instance as the existing `report_routes.py`. |
| **Database migration** | `alembic/versions/xxxx_create_domains_prompts.py` (or manual script) | Create both tables.                                                                                                                                     | Add FK from `prompt.domain_id → domain.id`.                            |

> **Why the MVP does not delete** or alter `report_routes.py`.  
> All discovery logic (via `GET /domains`) and creation logic lives in new files, leaving the core report API unchanged.

---

## 2. Front‑end – UI & store

| Piece                             | What it does                                                                                                                                                | Where to place                                                                                             |
| --------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| **Domain state**                  | In `useStore` add `domain: string` and a `setDomain(d)` setter.                                                                                             | `ui/src/store/useStore.ts`                                                                                 |
| **Domain selector component**     | Simple `<select>` that shows (`GET /domains`‑fetched) entries. On change calls `setDomain`.                                                                 | `ui/src/components/domain/DomainSelector.tsx`                                                              |
| **Place selector**                | Add `<DomainSelector />` to `App.tsx` header or top‑left of the side‑panel.                                                                                 | `ui/src/App.tsx`                                                                                           |
| **Adapter usage**                 | The code that constructs the platform adapter (`new OpenQuireAdapter(domain)`) should now receive the domain from the store instead of a hard‑coded string. | Update the adapter initialisation (likely in a top‑level context or wherever the adapter is instantiated). |
| **Fetching domains list on load** | On application start, call `/domains` (via `fetch`/axios) and populate the selector.                                                                        | `useEffect` inside `DomainSelector.tsx`.                                                                   |

> The adapter **still** talks to the same external OpenQuire APIs – but now it knows _which_ domain’s metadata (e.g. section names, intents, etc.) to use when it creates the payload.

---

## 3. Minimal “seed” data

Since the MVP will initially have only the **“site inspection”** domain, create a very small **seed** script (could be a one‑shot Python script or even a POST request from Postman) that:

```bash
curl -X POST localhost:8000/domains -H 'Content-Type: application/json' \
     -d '{"name":"site inspection","description":"PCA/Construction forms"}'
```

and optionally create a couple of prompts for that domain:

```bash
curl -X POST localhost:8000/prompts -H 'Content-Type: application/json' \
     -d '{"domain_id":1,"name":"Populate invoice","text":"..."}'
```

> Use this script in CI/Migrations to pre‑populate the DB before the first deployment.

---

## 4. Why this plan is safe and scalable

| Criterion                          | How MVP meets it                                                                                                                         |
| ---------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| **No disruption to existing flow** | `report_routes.py` remains untouched; the `storeFormSchema()` call keeps the exact payload you already ship.                             |
| **Future extensibility**           | Adding another domain → just POST to `/domains`; write a new adapter for it, no code changes to the core.                                |
| **Minimal risk**                   | The new router is isolated; the old API still works, so backward‑compatibility is guaranteed.                                            |
| **Operational simplicity**         | All domain‑specific data is in the DB – you can add, edit, or delete domains/prompts via simple REST calls or a small admin UI later on. |

---

## 5. Next steps (the work we’ll start with)

1. **Create the database tables** (`domains`, `prompts`) and add a migration file.
2. **Implement the routers** (`domains_routes.py`, `prompts_routes.py`) and mount them.
3. **Add a small CLI/seed script** that creates the “site inspection” domain (and a dummy prompt).
4. **Update the front‑end store** with `domain` and `setDomain`.
5. **Create the `DomainSelector` component** and add it to the UI.
6. **Refactor adapter usage** to use `useStore().domain`.
7. **Optional**: auto‑populate the selector by hitting `GET /domains` on component mount.

That’s all the minimal functionality needed for the **MVP**. Pagination, RBAC, charting, and other advanced features can be layered on later without breaking what we just built.
