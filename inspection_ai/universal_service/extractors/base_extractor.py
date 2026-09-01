import re
from typing import List

from ..models.evidence import Evidence, infer_data_type

RULE_BASED_PATTERNS = {
    "address": r"\d+\s+[\w\s]+(?:STREET|AVE|BLVD|RD|DR|LN|WAY|HWY|CT|PL|Boulevard|Street|Avenue|Road|Drive|Lane|Way|Highway|Court|Place|Parkway)[,\s]+(?:[\w\s]+,\s*)?[A-Z]{2}\s+\d{5}",
    "phone": r"\(? ?\d{3} ?\)?-?[-.\s]?\d{3}[-.\s]?\d{4}",
    "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    "date": r"\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2}",
    "dollar_amount": r"\$[\d,]+(?:\.\d{2})?",
    "percentage": r"\d+(?:\.\d+)?%",
    "square_footage": r"[\d,]+(?:\s*SF|\s*sq\s*ft|\s*square\s*feet?)",
    "voltage": r"\d+[-–]?\d*\s*(?:V|volts?|VAC)",
    "year": r"\b(?:19|20)\d{2}\b",
}

CATEGORY_RULES = {
    "property_information": [
        "owner",
        "address",
        "legal",
        "parcel",
        "account",
        "jurisdiction",
        "neighborhood",
        "fiduciary",
    ],
    "building_information": [
        "building",
        "area",
        "year_built",
        "property_type",
        "quality",
        "remodel",
        "feature",
    ],
    "building_systems": [
        "electrical",
        "plumbing",
        "hvac",
        "heating",
        "cooling",
        "panel",
        "voltage",
        "roof",
        "fire",
        "sprinkler",
        "alarm",
        "structural",
        "foundation",
        "boiler",
        "chiller",
        "elevator",
        "generator",
        "transformer",
        "duct",
        "ventilation",
        "water",
        "pipe",
        "heater",
    ],
    "financial_regulatory_information": [
        "tax",
        "value",
        "assessment",
        "exemption",
        "jurisdiction",
        "rate",
        "permit",
        "violation",
        "inspection",
        "appraisal",
        "levy",
        "valuation",
        "market",
    ],
}


def extract_with_rules(text: str, confidence: float = 0.85) -> List[dict]:
    extracted = []
    for field_name, pattern in RULE_BASED_PATTERNS.items():
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            extracted.append(
                {
                    "field_name": field_name,
                    "value": matches[0],
                    "confidence": confidence,
                }
            )
    return extracted


def categorize_field(field_name: str) -> str:
    field_lower = field_name.lower()
    for category, keywords in CATEGORY_RULES.items():
        if any(kw in field_lower for kw in keywords):
            return category
    return "unknown"


def parse_llm_fields(response) -> List[dict]:
    if not response:
        return []
    raw_fields = response.get("fields") or response.get("batch_results") or []
    result = []
    for item in raw_fields:
        if isinstance(item, dict) and item.get("name"):
            result.append(
                {
                    "field_name": item["name"],
                    "value": item.get("value"),
                    "confidence": float(item.get("conf", item.get("confidence", 0.0))),
                    "raw_text": item.get("raw_text"),
                }
            )
    return result


class BaseExtractor:
    def __init__(self, llm_client=None, config=None):
        self.llm = llm_client
        self.config = config

    def build_evidence(
        self,
        field_name: str,
        value,
        source_type: str,
        source_ref: str,
        report_id: str,
        session_id: str,
        batch_id: str,
        confidence: float,
        raw_text: str = None,
        document_hash: str = None,
        content_hash: str = None,
        file_id: str = None,
        document_id: str = None,
        tags: list = None,
        extraction_model: str = "unknown",
        category: str = None,
        subcategory: str = None,
        user_id: str = None,
    ) -> Evidence:
        if user_id is None:
            user_id = getattr(self, "user_id", None)
        return Evidence(
            id=f"evt.{source_type}.{report_id}.{source_ref}.{field_name}",
            evidence_batch_id=batch_id,
            session_id=session_id,
            report_id=report_id,
            file_id=file_id,
            document_id=document_id,
            user_id=user_id,
            source_type=source_type,
            source_ref=source_ref,
            document_hash=document_hash,
            content_hash=content_hash,
            field_name=field_name,
            value=value,
            data_type=infer_data_type(value),
            confidence=confidence,
            raw_text=(raw_text or "")[:500],
            category=category or categorize_field(field_name),
            subcategory=subcategory,
            tags=tags or [],
            extraction_model=extraction_model,
        )
