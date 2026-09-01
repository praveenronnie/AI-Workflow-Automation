"""Pydantic schemas for the Universal Form Automation API."""

from typing import Any, List, Optional, Dict

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    services: Dict[str, bool] = Field(default_factory=dict)


class UploadResponse(BaseModel):
    report_id: str
    session_id: str
    evidence_count: int
    evidence: List[Dict[str, Any]] = Field(default_factory=list)


class MappingResponse(BaseModel):
    report_id: str
    session_id: str
    mappings: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class FormSchemaRequest(BaseModel):
    form_schema: Dict[str, Any]
    report_id: Optional[str] = None
