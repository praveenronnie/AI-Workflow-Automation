"""
Configuration management using Pydantic Settings.
Loads from .env file with type validation and defaults.
"""

from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Paths
    storage_dir: Path = Field(default=Path("./storage"))

    # Retry
    max_retries: int = Field(default=3)
    retry_backoff_factor: int = Field(default=2)

    # Redis
    redis_host: str = Field(default="localhost")
    redis_port: int = Field(default=6379)
    redis_db: int = Field(default=0)

    # EasyOCR (used by Docling pipeline)
    easyocr_languages: List[str] = Field(default=["en"])
    easyocr_use_gpu: bool = Field(default=True)

    # Inference
    use_inference: bool = Field(default=False)
    inference_provider: str = Field(default="local")
    docling_modal_timeout: int = Field(default=600)

    # LLM
    llm_provider: str = Field(default="gemini")
    llm_model: str = Field(default="gemini-3.1-flash-lite")
    llm_url: str = Field(default="")
    llm_api_key: str = Field(default="")
    max_llm_tokens: int = Field(default=1000)
    llm_prompt_token_limit: int = Field(default=2000)

    # OpenAI Client
    openai_api_key: str = Field(default="")
    openai_base_url: str = Field(default="http://localhost:20128/v1")
    openai_base_model: str = Field(default="kr/claude-haiku-4.5")

    # Model Router (primary + fallback per flow)
    llm_default_primary: str = Field(default="nvidia/openai/gpt-oss-20b")
    llm_default_fallback: str = Field(default="gemini/gemini-3.1-flash-lite")
    llm_intent_primary: str = Field(default="kr/claude-haiku-4.5")
    llm_intent_fallback: str = Field(default="nvidia/openai/gpt-oss-120b")
    llm_field_mapping_primary: str = Field(default="kr/claude-haiku-4.5")
    llm_field_mapping_fallback: str = Field(default="gemini/gemini-3.5-flash")
    llm_pdf_primary: str = Field(default="gemini/gemini-3.1-flash-lite")
    llm_pdf_fallback: str = Field(default="kr/claude-haiku-4.5")
    llm_image_primary: str = Field(default="kr/claude-haiku-4.5")
    llm_image_fallback: str = Field(default="gemini/gemini-3.5-flash")
    llm_legacy_map_primary: str = Field(default="nvidia/openai/gpt-oss-120b")
    llm_legacy_map_fallback: str = Field(default="gemini/gemini-3.5-flash")

    # Retry + Circuit Breaker
    llm_max_retries: int = Field(default=3)
    llm_retry_backoff_factor: int = Field(default=2)
    llm_circuit_break_threshold: int = Field(default=5)
    llm_circuit_break_timeout: int = Field(default=60)

    # Batching
    llm_field_mapping_batch_size: int = Field(default=10)
    llm_image_batch_size: int = Field(default=10)

    # ----------------------------------------------------------------------
    #  Celery / task queue configuration
    # ----------------------------------------------------------------------
    celery_broker_url: str = Field(default="redis://localhost:6379/0")
    celery_result_backend: str = Field(default="redis://localhost:6379/1")

    # Concurrency tuning
        # Number of concurrent LLM batch calls (each batch processes up to
    # llm_field_mapping_batch_size fields). Increasing this raises throughput
    # when the LLM provider allows sufficient rate limits.
    max_concurrent_llm_calls: int = Field(default=10)
    map_section_concurrency: int = Field(default=8)
    # Bounded fan-out for the cheap per-field work (retrieval + rule + rerank)
    # inside a section. Prevents a dense section from spinning up unbounded
    # coroutines on CPU-bound work. Independent of the LLM pool.
    max_concurrent_fields_per_report: int = Field(default=50)
    embed_worker_pool: int = Field(default=4)
    batch_convert_pdf_min: int = Field(default=1)
    celery_concurrency: int = Field(default=4)
    max_concurrent_modal_jobs: int = Field(default=3)

    # EasyOCR
    easyocr_languages: List[str] = Field(default=["en"])
    easyocr_use_gpu: bool = Field(default=True)

    # NVIDIA
    nvidia_api_key: str = Field(default="")
    nvidia_url: str = Field(default="https://integrate.api.nvidia.com/v1")
    nvidia_model: str = Field(default="z-ai/glm-5.2")

    # Database (Postgres)
    db_name: str = Field(default="")
    db_host: str = Field(default="localhost")
    db_port: int = Field(default=5434)
    db_username: str = Field(default="")
    db_password: str = Field(default="")
    db_timeout: int = Field(default=30)
    db_pool_size: int = Field(default=10)
    db_max_overflow: int = Field(default=10)

        # Vector Database (Qdrant) — read from env (docker-compose sets VECTOR_DB_URL)
    vector_db_url: str = Field(default="http://localhost:6333")
    vector_db_api_key: str = Field(default="")
    vector_db_index_name: str = Field(default="universal_evidence")
    vector_db_dimension: int = Field(default=1024)
    embedding_model: str = Field(default="BAAI/bge-large-en-v1.5")
    # Score-fusion weights for hybrid retrieval (vector similarity + BM25)
    vector_weight: float = Field(default=0.7, ge=0.0, le=1.0)
    bm25_weight: float = Field(default=0.3, ge=0.0, le=1.0)
    rerank_top_k: int = Field(default=25, ge=1)

    # CORS (client origins allowed to call the API)
    cors_allow_origins: List[str] = Field(default=["*"])

    # JWT Auth
    jwt_secret_key: str = Field(default="change-me-in-production")
    jwt_algorithm: str = Field(default="HS256")
    jwt_access_token_expire_minutes: int = Field(default=60)
    jwt_refresh_token_expire_days: int = Field(default=7)

    # Report locks (shared reports: one interactive processor at a time)
    report_lock_ttl_seconds: int = Field(default=300)


# Singleton settings instance
_settings = Settings()


def get_settings() -> Settings:
    """Get the settings instance."""
    return _settings


# Helper functions
BASE_DIR = Path(__file__).resolve().parent


def get_report_storage_path(report_id: str) -> dict:
    """Get storage paths for a report."""
    base = Path(_settings.storage_dir) / report_id
    return {
        "original": base / "original",
        "processed": base / "processed",
        "images": base / "images",
        "json": base / "json",
    }


def prompt_loader(prompt_name: str) -> str:
    """Load prompt template from prompts directory."""
    prompt_path = BASE_DIR / "prompts" / f"{prompt_name}.txt"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file {prompt_path} not found.")
    return prompt_path.read_text(encoding="utf-8")
