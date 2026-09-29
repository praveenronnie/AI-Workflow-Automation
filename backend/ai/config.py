"""AI pipeline configuration: LLM routing, retrieval, embeddings, OCR."""

from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RagConfig(BaseSettings):
    """Configuration owned by the RAG pipeline (separate from system config)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_provider: str = Field(default="gemini")
    llm_model: str = Field(default="gemini-3.1-flash-lite")
    llm_url: str = Field(default="")
    llm_api_key: str = Field(default="")
    max_llm_tokens: int = Field(default=1000)
    llm_prompt_token_limit: int = Field(default=2000)

    openai_api_key: str = Field(default="")
    # LLM calls go through the OmniRoute gateway, which runs as a compose
    # service ("omniroute") on the same docker network. The service name is the
    # only correct default: "localhost" inside a container resolves to the
    # container itself, never to the gateway. Dev hosts that run uvicorn
    # directly (outside docker) override this with http://localhost:20128/v1.
    openai_base_url: str = Field(default="http://omniroute:20128/v1")
    openai_base_model: str = Field(default="kr/claude-haiku-4.5")

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

    llm_max_retries: int = Field(default=3)
    llm_retry_backoff_factor: int = Field(default=2)
    llm_circuit_break_threshold: int = Field(default=5)
    llm_circuit_break_timeout: int = Field(default=60)

    llm_field_mapping_batch_size: int = Field(default=10)
    llm_image_batch_size: int = Field(default=10)

    vector_db_url: str = Field(default="http://localhost:6333")
    vector_db_api_key: str = Field(default="")
    vector_db_index_name: str = Field(default="universal_evidence")
    vector_db_dimension: int = Field(default=1024)
    embedding_model: str = Field(default="BAAI/bge-large-en-v1.5")
    vector_weight: float = Field(default=0.7, ge=0.0, le=1.0)
    bm25_weight: float = Field(default=0.3, ge=0.0, le=1.0)
    rerank_top_k: int = Field(default=25, ge=1)

    easyocr_languages: List[str] = Field(default=["en"])
    easyocr_use_gpu: bool = Field(default=True)

    use_inference: bool = Field(default=False)
    inference_provider: str = Field(default="local")
    docling_modal_timeout: int = Field(default=600)

    nvidia_api_key: str = Field(default="")
    nvidia_url: str = Field(default="https://integrate.api.nvidia.com/v1")
    nvidia_model: str = Field(default="z-ai/glm-5.2")


_rag_config = RagConfig()


def get_rag_config() -> RagConfig:
    """Return the singleton RAG pipeline configuration."""
    return _rag_config