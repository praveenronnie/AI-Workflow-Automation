"""System-wide application settings loaded from environment variables."""

from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_storage_dir() -> Path:
    try:
        from backend.core.paths import REPO_ROOT

        return REPO_ROOT / "storage"
    except ImportError:  # pragma: no cover
        return Path(__file__).resolve().parents[2] / "storage"


class Settings(BaseSettings):
    """System configuration: database, broker, auth, CORS, storage paths."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Repo-root anchored so API / worker / beat all agree on the location no
    # matter which directory each process was started from.  Override with the
    # STORAGE_DIR env var if you need to relocate it.
    storage_dir: Path = Field(default_factory=lambda: _default_storage_dir())

    max_retries: int = Field(default=3)
    retry_backoff_factor: int = Field(default=2)

    redis_host: str = Field(default="localhost")
    redis_port: int = Field(default=6379)
    redis_db: int = Field(default=0)

    celery_broker_url: str = Field(default="redis://localhost:6379/0")
    celery_result_backend: str = Field(default="redis://localhost:6379/1")

    max_concurrent_llm_calls: int = Field(default=10)
    map_section_concurrency: int = Field(default=8)
    max_concurrent_fields_per_report: int = Field(default=50)
    embed_worker_pool: int = Field(default=4)
    batch_convert_pdf_min: int = Field(default=1)
    celery_concurrency: int = Field(default=4)
    max_concurrent_modal_jobs: int = Field(default=3)

    db_name: str = Field(default="")
    db_host: str = Field(default="localhost")
    db_port: int = Field(default=5434)
    db_username: str = Field(default="")
    db_password: str = Field(default="")
    db_timeout: int = Field(default=30)
    db_pool_size: int = Field(default=10)
    db_max_overflow: int = Field(default=10)

    cors_allow_origins: List[str] = Field(default=["*"])

    jwt_secret_key: str = Field(default="change-me-in-production")
    jwt_algorithm: str = Field(default="HS256")
    jwt_access_token_expire_minutes: int = Field(default=60)
    jwt_refresh_token_expire_days: int = Field(default=7)

    report_lock_ttl_seconds: int = Field(default=300)


_settings = Settings()


def get_settings() -> Settings:
    """Return the singleton settings instance."""
    return _settings


BASE_DIR = Path(__file__).resolve().parent.parent


def get_report_storage_path(report_id: str) -> dict:
    """Return the per-report storage layout."""
    base = Path(_settings.storage_dir) / report_id
    return {
        "original": base / "original",
        "processed": base / "processed",
        "images": base / "images",
        "json": base / "json",
    }


def prompt_loader(prompt_name: str) -> str:
    """Load a prompt template from the package prompts directory."""
    prompt_path = BASE_DIR / "prompts" / f"{prompt_name}.txt"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file {prompt_path} not found.")
    return prompt_path.read_text(encoding="utf-8")
