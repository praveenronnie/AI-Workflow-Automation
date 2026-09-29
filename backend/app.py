# Composition root: wires config, container, routers, and app lifecycle.

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.ai.config import get_rag_config
from backend.core.config import get_settings
from backend.core.container import UniversalServices, startup_services
from backend.core.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from backend.core.logging import configure_logging
from backend.database import init_db
from backend.features.auth.routes import router as auth_router
from backend.features.reports.routes import router as report_router
from backend.features.domains.routes import router as domain_router

configure_logging()
logger = logging.getLogger(__name__)

# Ensure the Qdrant vector store is enabled by default (production requirement).
os.environ.setdefault("USE_VECTOR_INDEX", "1")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Eagerly load every backing service at startup (PostgreSQL, LLM, Qdrant, Redis)."""
    services: UniversalServices = None

    # 1) PostgreSQL schema
    try:
        await init_db()
        logger.info("[STARTUP] PostgreSQL: ready")
    except Exception as e:  # noqa: BLE001
        logger.error("[STARTUP] PostgreSQL init failed: %s", e)

    # 1b) Domain catalogs (idempotent upsert of bundled manifests)
    try:
        from backend.database import AsyncSessionLocal
        from backend.domain_catalog.seed import seed_domain_catalogs

        async with AsyncSessionLocal() as seed_db:
            seeded = await seed_domain_catalogs(seed_db)
        logger.info("[STARTUP] Domain catalogs ensured: %s", seeded)
    except Exception as e:  # noqa: BLE001
        logger.error("[STARTUP] Domain catalog seeding failed: %s", e)

    # 2) LLM / Qdrant / Redis / Mapper (eager load, per-service status logged)
    try:
        services = await startup_services()
        status = {
            "llm": services.llm is not None,
            "vector_store": services.vector_store is not None,
            "redis": getattr(services.redis_cache, "client", None) is not None,
            "reranker": services.reranker is not None,
            "mapper": services.mapper is not None,
            "extractor_registry": services.extractor_registry is not None,
        }
        app.state.services_status = status
        logger.info("[STARTUP] Universal services loaded: %s", status)
    except Exception as e:  # noqa: BLE001
        logger.error("[STARTUP] Universal services startup failed: %s", e)
        services = None
        app.state.services_status = {}

    # Security-health warnings (fail the container logs loudly, keep booting so
    # the API is still usable in dev — a production gateway should block these).
    settings = get_settings()
    if settings.jwt_secret_key in ("", "change-me-in-production"):
        logger.warning(
            "[SECURITY] JWT_SECRET_KEY is not set to a strong value "
            "(current: %r) — set JWT_SECRET_KEY in .env before production.",
            settings.jwt_secret_key,
        )
    rag = get_rag_config()
    if not rag.llm_api_key and not rag.openai_base_url:
        logger.warning(
            "[SECURITY] No LLM API key configured — LLM calls will fail until "
            "LLM_API_KEY / LLM_URL or OPENAI_* are set."
        )

    yield

    # Graceful shutdown
    if services is not None:
        try:
            await services.shutdown()
            logger.info("[SHUTDOWN] Universal services stopped")
        except Exception as e:  # noqa: BLE001
            logger.error("[SHUTDOWN] error: %s", e)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    schemas = openapi_schema.get("components", {}).get("schemas", {})

    for schema in schemas.values():
        properties = schema.get("properties", {})

        for prop in properties.values():
            # list[UploadFile]
            if prop.get("type") == "array":
                items = prop.get("items", {})

                if items.get("contentMediaType") == "application/octet-stream":
                    items.pop("contentMediaType", None)
                    items["format"] = "binary"

            # UploadFile
            elif prop.get("contentMediaType") == "application/octet-stream":
                prop.pop("contentMediaType", None)
                prop["format"] = "binary"

    app.openapi_schema = openapi_schema
    return app.openapi_schema


def create_db_app() -> FastAPI:
    app = FastAPI(
        title="AI Report Automation API",
        description=(
            "Domain-agnostic universal form mapping backed by "
            "PostgreSQL + Qdrant + Redis + LLM."
        ),
        version="3.0.0",
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def request_id_middleware(request, call_next):
        """Correlate every log line (and response header) with one request id."""
        from backend.core.logging import new_request_id, request_id_var

        rid = request.headers.get("X-Request-ID") or new_request_id()
        token = request_id_var.set(rid)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = rid
        return response

    app.openapi = custom_openapi
    settings = get_settings()
    origins = settings.cors_allow_origins or ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if settings.jwt_secret_key == "change-me-in-production":
        logger.warning(
            "[SECURITY] JWT_SECRET_KEY is the default value — "
            "set a strong secret before deploying!"
        )
    app.include_router(auth_router)
    app.include_router(report_router)
    app.include_router(domain_router)

    @app.exception_handler(NotFoundError)
    async def _not_found(request, exc: NotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ConflictError)
    async def _conflict(request, exc: ConflictError):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(PermissionDeniedError)
    async def _forbidden(request, exc: PermissionDeniedError):
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @app.exception_handler(ValidationError)
    async def _validation(request, exc: ValidationError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/ready")
    async def ready():
        services = getattr(app.state, "services_status", {})
        # Worker liveness: the Celery beat maintenance task refreshes this key
        # every minute (120s TTL). Missing key => no worker/beat running.
        worker_alive = None
        try:
            from backend.ai.storage.cache import RedisCache

            cache = RedisCache()
            if cache.client is not None:
                worker_alive = cache.client.get("worker:heartbeat") is not None
        except Exception:  # noqa: BLE001
            worker_alive = None
        ready = bool(services) and any(services.values())
        return {
            "status": "ok" if ready else "degraded",
            "services": services,
            "worker_alive": worker_alive,
            "ready": ready,
        }

    return app


app = create_db_app()
