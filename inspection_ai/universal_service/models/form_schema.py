"""Universal form schema models."""

from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class FormField(BaseModel):
    """Universal form field."""

    id: str
    type: str = "text"
    label: str
    required: bool = False
    options: Optional[List[str]] = None
    validation: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class FormSection(BaseModel):
    """Universal form section."""

    id: str
    title: str
    fields: List[FormField]
    metadata: Optional[Dict[str, Any]] = None


class UniversalFormSchema(BaseModel):
    """Universal form schema."""

    form_id: str
    domain: Optional[str] = None
    version: str = "1.0"
    sections: List[FormSection]