"""
Data Transfer Objects for consistent field mapping across projects.
All extractions return data in this standardized format.
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Optional


@dataclass
class FieldDTO:
    canonical_name: str
    aliases: list = field(default_factory=list)
    value: Any = None
    confidence_score: float = 0.0
    evidence: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ProcessingStep:
    step: str
    status: str
    timestamp: str
    duration_ms: int = 0
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DocumentOutput:
    fields: list = field(default_factory=list)
    confidence_score: float = 0.0
    evidence: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ImageOutput:
    image_name: str
    caption: str = ""
    building_condition: str = ""
    roof_type: str = ""
    damage: str = ""
    tool: str = ""
    area: str = ""
    confidence_score: float = 0.0
    evidence: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MappingOutput:
    field_mappings: list = field(default_factory=list)
    unmapped_fields: list = field(default_factory=list)
    confidence_score: float = 0.0
    evidence: str = ""

    def to_dict(self) -> dict:
        return asdict(self)
