"""Extraction configuration for extractors."""

from pydantic import BaseModel


class ExtractionConfig(BaseModel):
    """Configuration for evidence extractors."""

    domain: str = "property_inspection"
    max_image_dim: int = 768
    image_batch_size: int = 10
    text_batch_size: int = 10
    llm_model: str = "kr/claude-sonnet-4.5"
    embedding_model: str = "BAAI/bge-large-en-v1.1"
    embedding_dimension: int = 1024
    rule_confidence: float = 0.85
    min_confidence_threshold: float = 0.6
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0