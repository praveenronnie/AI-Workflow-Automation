import logging
from pathlib import Path

from ..models.extraction_config import ExtractionConfig
from ..storage.evidence_store import EvidenceStore
from ..storage.report_registry import ReportRegistry
from ..storage.cache import RedisCache
from ..mapper.universal_mapper import UniversalMapper
from ..extractors.registry import ExtractorRegistry
from ..indexer.vector_store import UniversalVectorStore
from ..indexer.reranker import CrossEncoderReranker
from ..indexer.evidence_indexer import EvidenceIndexer
from ..indexer.bm25_index import BM25Index
from inspection_ai.services.llm_client import LLMClient
from inspection_ai.services.inference.modal_executor import ModalExecutor

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

        # 6. Extractor Registry
        try:
            logger.info("[START] Extractor Registry initialization")
            self.extractor_registry = ExtractorRegistry(
                config=self.config,
                vector_store=self.vector_store if self.retrieval_enabled else None,
            )
            logger.info("[OK]    Extractor Registry ready (pdf, image, zip)")
        except Exception as e:
            logger.error("[FAIL] Extractor Registry init failed: %s", e)
            self.extractor_registry = None

        # 7. Universal Mapper
        try:
            logger.info("[START] Universal Mapper initialization")
            self.mapper = UniversalMapper(
                llm_client=self.llm,
                vector_store=self.vector_store if self.retrieval_enabled else None,
                reranker=self.reranker,
                redis_client=self.redis_cache,
                domain=getattr(self.config, "domain", "property_inspection"),
                min_confidence=float(
                    getattr(self.config, "min_confidence_threshold", 0.6)
                ),
            )
            if self.indexer is not None:
                self.mapper.indexer = self.indexer
            logger.info("[OK]    Universal Mapper ready")
        except Exception as e:
            logger.error("[FAIL] Universal Mapper init failed: %s", e)
            self.mapper = None

        # 8. Modal Inference
        try:
            logger.info("[START] Modal Inference Intialization")
            self.modal_executor = ModalExecutor()
        except Exception as e:
            logger.error("[FAIL] Modal Inference startup failed: %s", e)
            self.modal_executor = None

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

    def build_mapper(self) -> UniversalMapper:
        """Build a fresh mapper instance (legacy method for compatibility)."""
        return self.mapper


_global_services: UniversalServices = None


async def startup_services(config: ExtractionConfig = None) -> UniversalServices:
    """Initialize and return the global services singleton (for dependency injection)."""
    global _global_services
    if _global_services is None:
        _global_services = UniversalServices(config)
        await _global_services.startup()
    return _global_services


def get_universal_services() -> UniversalServices:
    """Return the global services instance (lazy init fallback)."""
    global _global_services
    if _global_services is None:
        _global_services = UniversalServices()
        # Synchronous init for backward compatibility with non-async contexts
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            # Called from async context, services need explicit startup
            pass
        else:
            asyncio.run(_global_services.startup())
    return _global_services


def get_modal_executor() -> ModalExecutor:
    return get_universal_services().modal_executor
