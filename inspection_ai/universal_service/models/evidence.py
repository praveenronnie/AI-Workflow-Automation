"""Universal Evidence model."""

from pydantic import BaseModel, Field
from typing import Optional, Any, List


class Evidence(BaseModel):
    """Universal evidence object representing a single extracted fact."""

    id: str
    evidence_batch_id: str
    session_id: str
    report_id: str
    user_id: Optional[str] = None
    file_id: Optional[str] = None
    document_id: Optional[str] = None

    source_type: str
    source_ref: str = ""
    document_hash: Optional[str] = None
    content_hash: Optional[str] = None

    field_name: str
    value: Any
    data_type: str = "string"
    confidence: float = Field(ge=0.0, le=1.0)
    raw_text: Optional[str] = None

    category: Optional[str] = None
    subcategory: Optional[str] = None
    tags: List[str] = Field(default_factory=list)

    extraction_model: str = "unknown"
    timestamp: str = ""


def infer_data_type(value: Any) -> str:
    """Infer data type from value."""
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int) or isinstance(value, float):
        return "number"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "list"
    return "string"
