"""Request and response payloads for the reports feature."""

from pydantic import BaseModel


class ReportResponse(BaseModel):
    report_id: str
    session_id: str = None
    status: str
    file_count: int = 0
    created_at: str = None
    created: bool = False
    linked: bool = False
    restored: bool = False
class MappingPayload(BaseModel):
    form_schema: dict = None
    # The frontend selects a domain by NAME (the extension's domain selector is
    # name-based), so /map accepts either an explicit integer id or a name and
    # resolves to the id before running. This removes id-coupling on the client
    # and lets a missing/unknown selector fall back to the default domain.
    domain_id: int = None
    domain: str = None
class FormSchemaPayload(BaseModel):
    form_schema: dict
    scanned_payload: dict = None
    trigger_intent: bool = True
    source_url: str  # Required - website URL of the report being scanned
    source_domain: str = "openquire"
class CreateReportRequest(BaseModel):
    source_url: str = None
    source_domain: str = "openquire"
class LockPayload(BaseModel):
    lock_token: str = None
