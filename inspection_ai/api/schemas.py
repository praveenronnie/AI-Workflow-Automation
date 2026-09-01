from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class DocumentInfo(BaseModel):
    document_id: str = Field(..., description="File.id (UUID)")
    name: str = Field(..., description="Original filename")
    size: Optional[int] = Field(None, description="File size in bytes")
    type: Optional[str] = Field(None, description="MIME type")
    uploaded_at: datetime = Field(..., description="When the file was uploaded")


class ReportDetail(BaseModel):
    created_by: Optional[str] = Field(None, description="Report creator (user id)")
    report_id: str = Field(..., description="Report primary key (UUID)")
    report_url: str = Field(..., description="The website URL that owns this report")
    report_name: Optional[str] = Field(None, description="Human-readable name")
    domain: str = Field(..., description="Domain or website name")
    created_at: datetime = Field(..., description="Report creation timestamp")
    documents: List[DocumentInfo] = Field(
        default_factory=list,
        description="Metadata for every file uploaded to this report",
    )
    form_schema: Optional[Dict[str, Any]] = Field(
        None, description="Most recent form_schema.json for this report"
    )


class DomainBase(BaseModel):
    name: str = Field(..., description="Unique domain slug, e.g. 'site_inspection'")
    display_name: Optional[str] = Field(None, description="Human-readable name")
    description: Optional[str] = Field(None, description="Human-readable description")
    version: str = Field(default="1.0.0", description="Domain schema version")


class DomainCreate(DomainBase):
    """Payload used to register a brand‑new domain."""

    pass


class DomainOut(DomainBase):
    model_config = ConfigDict(from_attributes=True)
    id: int = Field(..., description="Database primary key")
    is_active: bool = Field(..., description="Whether the domain is enabled")
    created_at: datetime = Field(..., description="When the domain was created")
    updated_at: datetime = Field(..., description="Last update timestamp")


class PromptBase(BaseModel):
    name: str = Field(..., description="Short identifier for the prompt")
    text: str = Field(..., description="Full prompt text")
    is_default: bool = Field(
        default=False, description="Is this the default prompt for the domain?"
    )


class PromptCreate(PromptBase):
    domain_id: int = Field(..., description="Foreign key into domains.id")


class PromptOut(PromptBase):
    model_config = ConfigDict(from_attributes=True)
    id: int = Field(..., description="Database primary key")
    domain_id: int = Field(..., description="Foreign key into domains.id")
    created_at: datetime = Field(..., description="When the prompt was created")
    updated_at: datetime = Field(..., description="Last update timestamp")


# --------------------------------------------------------------------------- #
#  Domain manifest detail (sections, fields, aliases, intent)                #
# --------------------------------------------------------------------------- #
class DomainFieldIn(BaseModel):
    name: str = Field(..., description="Field label as it appears in reports")
    aliases: List[str] = Field(
        default_factory=list, description="Alternate phrasings for semantic retrieval"
    )
    intent: Optional[str] = Field(
        None, description="Intent tag from the domain taxonomy"
    )
    description: Optional[str] = Field(
        None, description="Short human-readable sentence describing this field"
    )


class DomainSectionIn(BaseModel):
    name: str = Field(..., description="Canonical section name")
    aliases: List[str] = Field(
        default_factory=list, description="Alternate section names for normalization"
    )
    order: int = Field(default=0, description="Display order within the domain")
    fields: List[DomainFieldIn] = Field(default_factory=list)


class DomainManifestIn(BaseModel):
    version: str = Field(default="1.0.0", description="Manifest version")
    section_count: int = Field(
        default=0, description="Number of sections in this manifest"
    )
    field_count: int = Field(default=0, description="Number of fields in this manifest")
    sections: List[DomainSectionIn] = Field(default_factory=list)


class DomainFieldOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int = Field(..., description="Database primary key")
    name: str = Field(..., description="Field label")
    aliases: List[str] = Field(default_factory=list)
    intent: Optional[str] = Field(None)
    description: Optional[str] = Field(None, description="Human-readable description")


class DomainSectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int = Field(..., description="Database primary key")
    name: str = Field(..., description="Canonical section name")
    aliases: List[str] = Field(default_factory=list)
    order: int = Field(default=0)
    fields: List[DomainFieldOut] = Field(default_factory=list)


class DomainManifestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int = Field(..., description="Database primary key")
    domain_id: int = Field(..., description="Foreign key into domains.id")
    version: str = Field(..., description="Manifest version")
    section_count: int = Field(default=0)
    field_count: int = Field(default=0)
    sections: List[DomainSectionOut] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
#  Domain update (partial)                                                    #
# --------------------------------------------------------------------------- #
class DomainUpdate(BaseModel):
    """Partial payload for ``PUT /domains/{id}``."""

    name: Optional[str] = Field(None, description="Unique domain slug")
    description: Optional[str] = Field(None, description="Human-readable description")
    version: Optional[str] = Field(None, description="Domain schema version")
    is_active: Optional[bool] = Field(None, description="Enable/disable the domain")


# --------------------------------------------------------------------------- #
#  Composite domain upload (identity + full section/field tree)               #
# --------------------------------------------------------------------------- #
class DomainUploadIn(BaseModel):
    """Payload for ``POST /domains/upload``.

    Merges the domain identity (from ``manifest.json``) with the full
    section -> field catalog tree. Upserts the domain by name and replaces
    the manifest for the given version atomically.
    """

    domain_name: str = Field(
        ..., description="Unique domain slug, e.g. 'pca_site_assessment'"
    )
    display_name: Optional[str] = Field(None, description="Human-readable name")
    version: str = Field(default="1.0.0", description="Domain + manifest version")
    description: Optional[str] = Field(None, description="Human-readable description")
    is_active: bool = Field(default=True, description="Whether the domain is enabled")
    sections: List[DomainSectionIn] = Field(
        default_factory=list,
        description="Full section -> field tree with aliases and intents",
    )


class DomainUploadOut(BaseModel):
    """Result of a successful composite upload."""

    domain_id: int = Field(..., description="Database primary key of the domain")
    manifest_id: int = Field(
        ..., description="Database primary key of the stored manifest"
    )
    domain_name: str = Field(..., description="Domain slug that was upserted")
    version: str = Field(..., description="Manifest version that was stored")
    section_count: int = Field(..., description="Number of sections stored")
    field_count: int = Field(..., description="Number of fields stored")
