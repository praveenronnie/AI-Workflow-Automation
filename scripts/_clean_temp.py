import json, pathlib

# Path to the manifest we want to clean
MANIFEST = pathlib.Path(r"d:/Projects/ai-report-automation/inspection_ai/domain_catalog/pca_site_assessment/temp.json")

# Simple blacklist of clearly out‑of‑domain or noisy aliases (expanded as you discover more)
BLACKLIST = {
    "mise en scene",
    "circumstance",
    "place setting",
    "stage setting",
    "pre",
    "questionnaire",
    "computer programme",
    "criminal maintenance",
    "political platform",
    "political program",
    "cosmopolitan",
    "oecumenical",
    "superior general",
    "full general",
    "tempest",
    "violent storm",
    "building block",
    "entranceway",
    "room access",
    "unit doors",
    "unit of measurement",
    "religious service",
    "robert william service",
    "service of process",
    "inspect and repair",
    "characteristic",
    "feature article",
    "feature film",
    "feature of speech",
    "window dressing",
    "give the sack",
    "head for the hills",
    "take to the woods",
    "chemical element",
    "elevated railway",
    "overhead railway",
    "ca inspection",
    "elevated element",
    "elevated railroad",
    "elevated railway",
    "overhead railway",
    "political program",
    "political platform",
    "computer programme",
}

def clean_aliases(aliases):
    """Return a cleaned list of aliases.
    * drop anything in the blacklist
    * drop aliases longer than 25 characters
    * keep only alphabetic + spaces (strip punctuation)
    * deduplicate while preserving order
    """
    cleaned = []
    seen = set()
    for a in aliases:
        a_low = a.lower().strip()
        if a_low in BLACKLIST:
            continue
        if len(a_low) > 25:
            continue
        # keep simple words/phrases (allow spaces but no special symbols)
        if any(ch for ch in a_low if not (ch.isalnum() or ch.isspace())):
            continue
        if a_low not in seen:
            seen.add(a_low)
            cleaned.append(a)
    return cleaned

def make_description(name: str, intent: str | None) -> str:
    """Produce a concise, human‑readable description.
    Example: "The Water Meter Size field records utilities capacity."
    """
    base = f"The {name} field"
    if intent:
        return f"{base} records {intent.replace('_', ' ')}."
    return f"{base} records data."

def main() -> int:
    try:
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[ERROR] Could not load manifest: {exc}")
        return 1

    for section in data:
        for field in section.get("fields", []):
            # Clean aliases
            original = field.get("aliases", [])
            field["aliases"] = clean_aliases(original)
            # Update description if still the generic one
            desc = field.get("description", "")
            if desc.startswith("A field capturing"):
                field["description"] = make_description(field["name"], field.get("intent"))

    # Write back (overwrite the same temp.json)
    MANIFEST.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print("[OK] Cleaned manifest written to", MANIFEST)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
