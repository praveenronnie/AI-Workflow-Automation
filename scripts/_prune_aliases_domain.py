import json, pathlib, re

MANIFEST = pathlib.Path(r"d:/Projects/ai-report-automation/backend/inspection_ai/domain_catalog/pca_site_assessment/temp.json")

# Domain‑specific keyword whitelist – terms that are relevant to building, site, construction, etc.
DOMAIN_KEYWORDS = {
    "building",
    "site",
    "property",
    "construction",
    "inspection",
    "roof",
    "roofing",
    "structure",
    "foundation",
    "foundation",
    "door",
    "doors",
    "window",
    "windows",
    "wall",
    "walls",
    "floor",
    "floors",
    "paving",
    "curbing",
    "slope",
    "topography",
    "drainage",
    "storm",
    "water",
    "utility",
    "utilities",
    "elevated",
    "element",
    "code",
    "violation",
    "life",
    "safety",
    "condition",
    "maintenance",
    "quality",
    "parking",
    "access",
    "entry",
    "exit",
    "egress",
    "ingress",
    "balcony",
    "patio",
    "exterior",
    "interior",
    "grade",
    "elevation",
    "grade",
    "material",
    "age",
    "type",
    "record",
    "recording",
    "recorded",
    "field",
    "measure",
    "capacity",
    "size",
    "dimension",
    "area",
    "height",
    "width",
    "depth",
    "percent",
    "percentage",
    "number",
    "count",
    "level",
    "rating",
    "status",
    "site_improvements",
    "building_envelope",
    "code_violation",
    "life_safety",
    "condition",
    "property_information",
    "utilities_capacity",
    "roofing",
    "site_improvements",
    "building_envelope",
    "code_violation",
    "life_safety",
    "condition",
    "property_information",
    "utilities_capacity",
    "roofing",
}

# compile regex for quick search
keyword_pattern = re.compile(r"(" + r"|".join(re.escape(k) for k in DOMAIN_KEYWORDS) + r")", re.IGNORECASE)

def is_domain_alias(alias: str) -> bool:
    # keep if any domain keyword appears as a whole word
    return bool(keyword_pattern.search(alias))

def prune_aliases(aliases, field_name):
    """Return a cleaned list of aliases.
    Keep an alias if:
      * it contains any domain keyword, OR
      * it shares a word with the field name (e.g., "roof" in "Roof Type").
    Also drop duplicates and limit length.
    """
    cleaned = []
    seen = set()
    field_words = {w.lower() for w in field_name.split()}
    for a in aliases:
        a_low = a.lower().strip()
        # keep if contains domain keyword
        keep = is_domain_alias(a_low)
        # or shares a word with field name
        if not keep:
            alias_words = {w for w in re.split(r"\W+", a_low) if w}
            if alias_words & field_words:
                keep = True
        if not keep:
            continue
        # length guard
        if len(a_low) > 30:
            continue
        if a_low not in seen:
            seen.add(a_low)
            cleaned.append(a)
    return cleaned

def improve_description(name: str, intent: str | None) -> str:
    """Create a concise description for building/site assessment.
    Avoid repeating the word "information".
    """
    base = f"The {name} field"
    if intent:
        intent_clean = intent.replace('_', ' ')
        # If intent already mentions "information", don't add it again
        if "information" in intent_clean:
            return f"{base} records {intent_clean} for building/site assessment."
        return f"{base} records {intent_clean} information for building/site assessment."
    return f"{base} records data for building/site assessment."

def main():
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for section in data:
        for field in section.get("fields", []):
            # prune aliases using field name for additional matching
            original = field.get("aliases", [])
            field_name = field.get("name", "")
            field["aliases"] = prune_aliases(original, field_name)
            # update description if it is still generic (does not already mention assessment)
            desc = field.get("description", "")
            if "assessment" not in desc.lower():
                field["description"] = improve_description(field_name, field.get("intent"))
    # write back to same file
    MANIFEST.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print("[OK] Domain‑specific alias pruning and description update complete.")

if __name__ == "__main__":
    raise SystemExit(main())
