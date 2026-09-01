import re
from typing import List, Dict, Any, Optional

from ..models.evidence import Evidence
from ..models.form_schema import FormField


SYNONYM_GROUPS = {
    "address": ["address", "addr", "street", "location", "site address"],
    "owner": ["owner", "owner_name", "prop_owner", "responsible party"],
    "phone": ["phone", "telephone", "contact_number", "phone_number"],
    "email": ["email", "e-mail", "email_address"],
    "parcel": ["parcel", "apn", "parcel_id", "parcel_number"],
    "year_built": ["year_built", "year built", "construction_year", "built"],
    "square_footage": ["area", "square_footage", "sqft", "sf", "building_area", "size"],
    "voltage": ["voltage", "volts", "electrical"],
    "roof_type": ["roof_type", "roof type", "roof"],
    "property_type": ["property_type", "bldg_type", "building_type", "usage"],
    "market_value": ["market_value", "market value", "mv"],
    "assessed_value": ["assessed_value", "assessment", "assessed"],
    "tax": ["tax", "taxes", "property_tax"],
}


def normalize(token: str) -> str:
    return re.sub(r"[^a-z0-9]", "", token.lower())


def field_tokens(field: FormField) -> List[str]:
    tokens = []
    for part in [field.label, field.id, field.type]:
        if part:
            tokens.extend(part.split())
    for opt in field.options or []:
        tokens.extend(opt.split())
    return [normalize(t) for t in tokens if t]


def evidence_keywords(evt: Evidence) -> List[str]:
    tokens = [evt.field_name]
    if evt.raw_text:
        tokens.extend(evt.raw_text.split())
    if isinstance(evt.value, str):
        tokens.append(evt.value)
    normalized = []
    for tok in tokens:
        normalized.extend(normalize(t) for t in tok.split())
    return normalized


def match_evidence(field: FormField, evidence: List[Evidence]) -> Optional[Dict[str, Any]]:
    field_token_set = set(field_tokens(field))
    if not field_token_set:
        return None

    expanded = set(field_token_set)
    for token in field_token_set:
        for canonical, syns in SYNONYM_GROUPS.items():
            if token in syns or any(token in s for s in syns):
                expanded.update(syns)

    scored = []
    for evt in evidence:
        # Keep low-confidence evidence as a fallback candidate, but rank it
        # below higher-confidence hits via the sort key below.
        ev_tokens = set(evidence_keywords(evt))
        overlap = ev_tokens & expanded
        if overlap:
            score = len(overlap) / max(len(field_token_set), 1)
            scored.append((evt, score, overlap))

    if not scored:
        return None

    scored.sort(key=lambda x: (x[1], x[0].confidence), reverse=True)
    best_evt, score, overlap = scored[0]

    value = best_evt.value
    if field.type in ("dropdown", "radio", "multi_select") and field.options:
        value = _resolve_option(field.options, value)
        confidence = min(0.98, 0.66 + score * 0.3 + best_evt.confidence * 0.14)
    else:
        confidence = min(0.97, 0.62 + score * 0.3 + best_evt.confidence * 0.18)

    return {
        "value": value,
        "confidence": round(confidence, 3),
        "reasoning": "Rule-based match via overlapping tokens: " + str(sorted(overlap)[:4]),
        "sources": [best_evt.source_ref],
    }


def _resolve_option(options: List[Any], value: Any) -> Any:
    """Nearest-option match for dropdown-style fields.

    Falls back to the raw value when nothing matches so downstream
    ``resolve_option_id`` can still attempt its own mapping.
    """
    norm_value = normalize(str(value))
    if not norm_value:
        return value
    for opt in options:
        if normalize(str(opt)) == norm_value:
            return opt
    # Substring containment both ways (handles "CommerciallY developed" etc.)
    for opt in options:
        no = normalize(str(opt))
        if no and (no in norm_value or norm_value in no):
            return opt
    # Fuzzy token-overlap match (handles "Appears legal, non conforming" vs
    # "Appears legal, non-conforming" — separator differences collapse after
    # normalizing each whitespace-delimited token). Only accept a clear winner:
    # the option whose token set has the most overlap with the value must beat
    # every other option strictly.
    def _tokens(raw: Any) -> set:
        return {normalize(t) for t in str(raw).split() if normalize(t)}

    value_tokens = _tokens(value)
    best_opt, best_overlap = None, 0
    for opt in options:
        overlap = len(value_tokens & _tokens(opt))
        if overlap > best_overlap:
            best_opt, best_overlap = opt, overlap
    # Require a meaningful overlap (at least one shared token) and, to avoid
    # grabbing a one-token coincidence, only trust it when the overlap covers
    # a real share of the option's own tokens.
    if best_opt is not None and best_overlap > 0:
        opt_total = len(_tokens(best_opt))
        if best_overlap >= 2 or opt_total == 1:
            return best_opt
    return value


class FieldMatcher:
    def match_evidence(self, field, evidence):
        return match_evidence(field, evidence)