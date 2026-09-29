# FormIQ — Deployment Runbook (Hetzner + Cloudflare)

Target: one Hetzner Cloud VM running the whole stack via
`docker-compose.prod.yml` (Caddy terminates TLS), Cloudflare in front for DNS,
WAF and rate limiting.

## 0. Topology

```
Cloudflare (DNS, WAF, rate limit, TLS Full-strict)
        |  https://{$API_DOMAIN}
   Caddy (Let's Encrypt, 80/443)          formiq-caddy
        |  http://api:8000
   FastAPI (uvicorn, 1 worker)            formiq-api      -+
   Celery worker (concurrency 2)          formiq-worker   -+ shared uploads_data
   Celery beat (heartbeat + sweeper)      formiq-beat      |  (/app/storage)
        |
   Postgres 16 . Redis 7 . Qdrant          (no public ports)
        |
   OmniRoute (LLM gateway, :20128)         formiq-omniroute + omniroute_data
```

Every inter-service URL is a compose service name. `ENV=production` makes the API
**refuse to boot** if any of `DB_HOST`, `REDIS_HOST`, `VECTOR_DB_URL` or
`OPENAI_BASE_URL` resolves to loopback, if `JWT_SECRET_KEY` is the default, or if
`CORS_ALLOW_ORIGINS` is `*`. That check is the tripwire for "it works on my
machine".

## 1. VM sizing

| | Minimum | Recommended |
|---|---|---|
| Type | CX32 (4 vCPU / 8 GB) | CX42 (8 vCPU / 16 GB) |
| Disk | 80 GB | 160 GB |
| Swap | 4 GB | 4 GB |

The API image installs torch + docling + easyocr + sentence-transformers (~7 GB of
pip layers). **Do not build on a 4 GB / 40 GB CX22** — the pip step OOMs. Prefer
building in CI and pulling from GHCR; building on the server is the fallback.

## 2. Provision the VM

```bash
# as root
adduser --disabled-password --gecos "" deploy && usermod -aG sudo,docker deploy
ufw allow 22,80,443/tcp && ufw enable
apt-get update && apt-get install -y fail2ban unattended-upgrades
fallocate -l 4G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
curl -fsSL https://get.docker.com | sh      # docker + compose plugin
```

## 3. Cloudflare DNS + TLS

1. `A  api.<yourdomain>  ->  <server-ip>` (proxy optional).
2. **Certificate issuance:** with the record **DNS-only (grey cloud)**, Caddy
   obtains a Let's Encrypt cert over HTTP-01 automatically. To use the orange
   cloud from day one, switch to the DNS-01 challenge (Cloudflare API token) or
   install a Cloudflare **Origin certificate** in Caddy and set
   **SSL/TLS -> Full (strict)**.
3. Enable Always Use HTTPS and Minimum TLS 1.2.
4. WAF -> managed rules on; add a rate-limit rule for `/auth/token` and
   `/auth/register` (e.g. 10 req/min per IP) to back up the app's Redis limiter.
5. Cache rules: bypass cache for `/reports*` and `/auth*`.
6. R2 (optional, backups): bucket + Object Read/Write token; bucket CORS only if
   uploads ever move to R2.

## 4. Secrets on the server

```bash
git clone git@github.com:praveenronnie/AI-Workflow-Automation.git formiq
cd formiq && cp .env.example .env && chmod 600 .env
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # JWT_SECRET_KEY
```

Fill `.env` (never commit it):

| Key | Value |
|---|---|
| `API_DOMAIN` | `api.<yourdomain>` (must NOT be the placeholder) |
| `DB_NAME` / `DB_USERNAME` / `DB_PASSWORD` | strong password (`openssl rand -base64 24`) |
| `JWT_SECRET_KEY` | generated above |
| `CORS_ALLOW_ORIGINS` | `["chrome-extension://<EXTENSION_ID>"]` |
| `OPENAI_API_KEY` | OmniRoute gateway key (see section 5) |
| `OPENAI_BASE_MODEL` | `kr/claude-haiku-4.5` |
| `NVIDIA_API_KEY` | required by the `nvidia/*` fallback models |
| `MODAL_TOKEN_ID` / `MODAL_TOKEN_SECRET` / `HF_TOKEN` | Modal inference |
| `USE_INFERENCE` / `INFERENCE_PROVIDER` | `True` / `modal` |
| `OMNIROUTE_INITIAL_PASSWORD` | strong value — never `CHANGEME` |
| `R2_*` | optional (backups) |

## 5. OmniRoute (LLM gateway) — the one stateful gotcha

Every LLM call is routed through OmniRoute, and its provider connections + keys
live in the `omniroute_data` volume (`/app/data/storage.sqlite`, `server.env`).
A **fresh** volume has no providers, so mapping silently degrades. Choose one:

- **Copy the configured volume** (fastest; keeps current providers/tokens):

  ```bash
  # on the machine that works today
  docker run --rm -v ai-report-automation_omniroute-data:/data -v "$PWD":/backup \
    alpine tar czf /backup/omniroute-data.tgz -C /data .
  # on the server, after the first `up` created the volume
  docker compose -f docker-compose.prod.yml stop omniroute
  docker run --rm -v ai-report-automation_omniroute-data:/data -v "$PWD":/backup \
    alpine sh -c "cd /data && tar xzf /backup/omniroute-data.tgz"
  docker compose -f docker-compose.prod.yml up -d omniroute
  ```

- **Or bootstrap fresh:** start the stack, open the OmniRoute UI through an SSH
  tunnel (temporarily publish port 20128: `ssh -L 20128:localhost:20128
  deploy@<ip>`), log in with `OMNIROUTE_INITIAL_PASSWORD`, add provider
  connections, mint an API key, set it as `OPENAI_API_KEY` in `.env`, then
  restart `api` and `worker`.

Verify from inside the network (expect `200 ok`):

```bash
docker exec formiq-api python -c "import httpx;from backend.ai.config import get_rag_config as g;print(httpx.get(g().openai_base_url.replace('/v1','') + '/healthz', timeout=5).text)"
```

Note: `/v1/models` is restricted to dashboard keys on OmniRoute — `/ready` probes
`/healthz` instead, and a real chat completion is the true end-to-end check.

## 6. Deploy

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps     # api needs ~3-4 min cold start
curl -s https://$API_DOMAIN/ready
# expect services all true, worker_alive true, llm_gateway true, ready true
```

`migrate` runs `alembic upgrade head` once and must exit 0 before `api` starts.

## 7. Go-live gate

```bash
python testing/runner.py https://api.<yourdomain>    # 14 suites (E2E needs Modal)
python tests/smoke_api.py https://api.<yourdomain>    # 31 API checks
python scripts/build_extension_prod.py --api-domain api.<yourdomain>
```

Then a real browser pass: load `dist/formiq-extension-<version>.zip` unpacked,
login -> create report -> upload PDF -> `/map` -> review values -> apply.
Confirm `/ready` reports `llm_gateway: true` and `worker_alive: true`.

## 8. Backups + monitoring

```bash
# daily 03:00 UTC: Postgres dump -> R2 (rclone), then a Qdrant snapshot
docker exec formiq-postgres pg_dump -U "$DB_USERNAME" "$DB_NAME" | gzip | \
  rclone rcat r2:form-iq/backups/pg-$(date +%F).sql.gz
curl -X POST http://localhost:6333/snapshots
```

- Uptime check on `https://$API_DOMAIN/ready` every minute (Cloudflare Health
  Check or UptimeRobot); alert on non-200 or `worker_alive: false`.
- Alert on disk > 80 % and on container restarts.
- Log rotation is capped in compose (`max-size: 10m`, 3-5 files).
- **Restore drill** before go-live: restore the dump into a scratch container and
  run `tests/smoke_api.py` against it.

## 9. Updates + rollback

```bash
git pull && docker compose -f docker-compose.prod.yml up -d --build
# rollback: git checkout <previous-tag> + same command. Migrations are
# forward-only, so take a dump before any schema change.
```

Tag the previous images (`docker tag formiq-api:latest formiq-api:prev`) so a bad
release can be re-pointed without a rebuild.
