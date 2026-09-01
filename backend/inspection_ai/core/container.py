"""Dependency container: builds and owns every backing service at startup.

Replaces ad-hoc module singletons; the instance lives on ``app.state`` and is
accessed through :func:`get_universal_services` until callers migrate.
"""

import asyncio
import logging
from pathlib import Path

from inspection_ai.ai.models.extraction_config import ExtractionConfig
from inspection_ai.ai.providers.inference.modal_executor import ModalExecutor
from inspection_ai.ai.providers.llm_client import LLMClient
from inspection_ai.ai.retrieval.bm25_index import BM25Index
from inspection_ai.ai.retrieval.evidence_indexer import EvidenceIndexer
from inspection_ai.ai.retrieval.reranker import CrossEncoderReranker
from inspection_ai.ai.retrieval.vector_store import UniversalVectorStore
from inspection_ai.ai.storage.cache import RedisCache
from inspection_ai.ai.storage.evidence_store import EvidenceStore
from inspection_ai.ai.storage.report_registry import ReportRegistry
from inspection_ai.ai.mapping.universal_mapper import UniversalMapper
from inspection_ai.ai.extraction.registry import ExtractorRegistry

logger = logging.getLogger(__name__)


class UniversalServices:
    """Container for all universal service dependencies with lifecycle management."""

    def __init__(self, config: ExtractionConfig = None):
        self.config = config or ExtractionConfig()
        self.storage_dir = Path(
            getattr(self.config, "storage_dir", None) or "/tmp/universal_uploads"
        )
        self._started = False

        # Lazy-initialized attributes
        self.llm: LLMClient = None
        self.vector_store: UniversalVectorStore = None
        self.store: EvidenceStore = None
        self.registry: ReportRegistry = None
        self.reranker: CrossEncoderReranker = None
        self.indexer: EvidenceIndexer = None
        self.redis_cache: RedisCache = None
        self.extractor_registry: ExtractorRegistry = None
        self.mapper: UniversalMapper = None
        self.use_vector = True
        self.modal_executor: ModalExecutor = None

    async def startup(self) -> None:
        """Initialize all services with proper logging. Called during app startup."""
        if self._started:
            logger.info("UniversalServices already started, skipping.")
            return

        logger.info("=" * 50)
        logger.info("Universal Service Startup Sequence")
        logger.info("=" * 50)

        # 1. LLM Client (critical for mapping, non-critical for extraction)
        try:
            logger.info("[START] LLM Client initialization")
            self.llm = LLMClient()
            logger.info("[OK]    LLM Client ready")
        except Exception as e:
            logger.warning("[WARN] LLM Client init failed: %s", e)

        # 2. PostgreSQL (via SQLAlchemy pool) - logged by SQLAlchemy via pool_pre_ping
        logger.info("[OK]    PostgreSQL connection pool configured (auto-ping enabled)")

        # 3. Vector Store / Reranker (optional, used for dense retrieval)
        if self.use_vector:
            try:
                logger.info("[START] Vector Store (Qdrant) initialization")
                self.vector_store = UniversalVectorStore()
                logger.info("[OK]    Vector Store connected, collection ready")
            except Exception as e:
                logger.warning("[WARN] Vector Store init failed: %s", e)
                self.vector_store = None

            try:
                logger.info("[START] Reranker (cross-encoder) initialization")
                self.reranker = CrossEncoderReranker()
                logger.info("[OK]    Reranker ready")
            except Exception as e:
                logger.warning("[WARN] Reranker init failed: %s", e)
                self.reranker = None

            self.indexer = (
                EvidenceIndexer(self.vector_store, bm25_index=BM25Index())
                if self.vector_store
                else None
            )
        else:
            logger.info("[INFO]  Vector retrieval disabled (USE_VECTOR_INDEX != 1)")
            self.vector_store = None
            self.reranker = None
            self.indexer = None

        # 4. Redis Cache (optional)
        try:
            logger.info("[START] Redis Cache initialization")
            self.redis_cache = RedisCache()
            if self.redis_cache.client:
                logger.info("[OK]    Redis Cache connected")
            else:
                logger.info("[WARN]  Redis Cache not connected (cache disabled)")
        except Exception as e:
            logger.warning("[WARN] Redis Cache init failed: %s", e)
            self.redis_cache = None

        # 5. Storage directories and flat-file stores
        try:
            logger.info("[START] Local storage initialization")
            self.store = EvidenceStore(self.storage_dir / "evidence")
            self.registry = ReportRegistry(self.storage_dir / "contexts")
            logger.info("[OK]    Local storage ready at %s", self.storage_dir)
        except Exception as e:
            logger.error("[FAIL] Local storage init failed: %s", e)
            self.store = None
            self.registry = None

        # 6. Modal Inference (created before extractors so they can share it)
        try:
            logger.info("[START] Modal Inference initialization")
            self.modal_executor = ModalExecutor()
        except Exception as e:
            logger.error("[FAIL] Modal Inference startup failed: %s", e)
            self.modal_executor = None

        # 7. Extractor Registry (reuses container llm + modal_executor)
        try:
            logger.info("[START] Extractor Registry initialization")
            self.extractor_registry = ExtractorRegistry(
                config=self.config,
                vector_store=self.vector_store if self.retrieval_enabled else None,
                llm=self.llm,
                modal_executor=self.modal_executor,
            )
            logger.info(
                "[OK]    Extractor Registry ready (pdf, image, handwritten, zip)"
            )
        except Exception as e:
            logger.error("[FAIL] Extractor Registry init failed: %s", e)
            self.extractor_registry = None

        # 8. Universal Mapper
        try:
            logger.info("[START] Universal Mapper initialization")
            self.mapper = self.build_mapper(
                domain=getattr(self.config, "domain", "property_inspection"),
                min_confidence=float(
                    getattr(self.config, "min_confidence_threshold", 0.6)
                ),
            )
            logger.info("[OK]    Universal Mapper ready")
        except Exception as e:
            logger.error("[FAIL] Universal Mapper init failed: %s", e)
            self.mapper = None

        self._started = True
        logger.info("=" * 50)
        logger.info("Startup Complete - Services status:")
        logger.info("  LLM:          %s", "READY" if self.llm else "UNAVAILABLE")
        logger.info("  Postgres:     POOL_OK")
        logger.info(
            "  Vector(Qdrant): %s", "READY" if self.vector_store else "UNAVAILABLE"
        )
        logger.info("  Reranker:     %s", "READY" if self.reranker else "UNAVAILABLE")
        logger.info(
            "  Redis:        %s", "READY" if self.redis_cache else "UNAVAILABLE"
        )
        logger.info("  Mapper:       %s", "READY" if self.mapper else "UNAVAILABLE")
        logger.info("=" * 50)

        logger.info(
            "Modal Inference:     %s", "READY" if self.modal_executor else "UNAVAILABLE"
        )

    async def shutdown(self) -> None:
        """Clean up resources on app shutdown."""
        if not self._started:
            return

        logger.info("Shutting down Universal Services...")
        # None of our services have explicit close(), they use lazy connection pools
        self._started = False
        logger.info("Shutdown complete.")

    @property
    def retrieval_enabled(self) -> bool:
        """Whether dense vector retrieval is available."""
        return self.use_vector and self.vector_store is not None

    def get_extractor(self, input_type: str):
        """Return the shared extractor singleton for a file type."""
        if self.extractor_registry is None:
            self.extractor_registry = ExtractorRegistry(
                config=self.config,
                vector_store=self.vector_store if self.retrieval_enabled else None,
                llm=self.llm,
                modal_executor=self.modal_executor,
            )
        return self.extractor_registry.get(input_type)

    def build_mapper(
        self,
        domain: str = None,
        min_confidence: float = 0.6,
        form_type: str = None,
    ) -> UniversalMapper:
        """Build a lightweight per-report mapper from the shared dependencies.

        The mapper itself is cheap and holds per-report state (domain, evidence,
        section-intent cache), so it must be fresh per report — but its heavy
        dependencies (LLM, Qdrant, reranker, Redis) are the container singletons.
        """
        mapper = UniversalMapper(
            llm_client=self.llm,
            vector_store=self.vector_store if self.retrieval_enabled else None,
            reranker=self.reranker,
            redis_client=self.redis_cache,
            domain=domain or getattr(self.config, "domain", "property_inspection"),
            form_type=form_type,
            min_confidence=min_confidence,
        )
        if self.indexer is not None:
            mapper.indexer = self.indexer
            mapper.bm25_index = self.indexer.bm25_index
        return mapper


_global_services: UniversalServices = None


def warmup_services(config: ExtractionConfig = None) -> UniversalServices:
    """Build and start the process-wide container once (blocking).

    Used by the Celery worker bootstrap (``worker_process_init``) so every task
    in a worker process reuses the same warmed services instead of re-initializing
    per job.
    """
    global _global_services
    if _global_services is None:
        _global_services = UniversalServices(config)
        asyncio.run(_global_services.startup())
    elif not _global_services._started:
        asyncio.run(_global_services.startup())
    return _global_services


async def startup_services(config: ExtractionConfig = None) -> UniversalServices:
    """Initialize and return the global services singleton (for dependency injection)."""
    global _global_services
    if _global_services is None:
        _global_services = UniversalServices(config)
        await _global_services.startup()
    return _global_services


def get_universal_services() -> UniversalServices:
    """Return the process-wide container (warmed by lifespan or worker bootstrap).

    Falls back to lazy seeding for scripts/tests; runtime paths (API lifespan,
    Celery ``worker_process_init``) warm the container first.
    """
    global _global_services
    if _global_services is None or not _global_services._started:
        warmup_services()
    return _global_services


def get_modal_executor() -> ModalExecutor:
    return get_universal_services().modal_executor
