from pathlib import Path
from typing import Dict

PROMPT_DIR = Path(__file__).parent


class PromptRegistry:
    def __init__(self):
        self.cache: Dict[str, str] = {}
        self.ensure_base_prompts()

    @staticmethod
    def ensure_base_prompts():
        base_dir = PROMPT_DIR / "base"
        base_dir.mkdir(parents=True, exist_ok=True)

    def get(self, domain: str, prompt_type: str) -> str:
        key = f"{domain}.{prompt_type}"

        if key not in self.cache:
            candidate = PROMPT_DIR / domain / f"{prompt_type}.txt"
            if not candidate.exists():
                candidate = PROMPT_DIR / "base" / f"{prompt_type}.txt"
            if not candidate.exists():
                raise FileNotFoundError(f"No prompt found for {key}")

            self.cache[key] = candidate.read_text(encoding="utf-8")

        return self.cache[key]

    def register(self, domain: str, prompt_type: str, prompt: str):
        self.cache[f"{domain}.{prompt_type}"] = prompt


_registry = PromptRegistry()


def get_extraction_prompt(domain: str = "property_inspection") -> str:
    return _registry.get(domain, "extraction")


def get_mapping_prompt(domain: str = "property_inspection") -> str:
    return _registry.get(domain, "mapping")


def get_image_prompt(domain: str = "property_inspection") -> str:
    return _registry.get(domain, "image_analysis")


def render_mapping_prompt(
    domain: str, field, evidence_pack: Dict, section_name: str = "", field_description: str = ""
) -> str:
    template = _registry.get(domain, "mapping")
    evidence = evidence_pack.get("evidence", []) if isinstance(evidence_pack, dict) else []
    evidence_text = "\n".join(
        "{source} | {field_name}: {value} | {raw}".format(
            source=e.get("source", ""),
            field_name=e.get("field_name", ""),
            value=e.get("value", ""),
            raw=(e.get("raw") or "")[:500],
        )
        for e in evidence
    )
    options = getattr(field, "options", None) or []
    label = getattr(field, "label", "") or ""
    ftype = getattr(field, "type", "text") or "text"
    # Pull description from the FormField.metadata dict, if the caller did not
    # supply one explicitly.
    if not field_description:
        metadata = getattr(field, "metadata", None) or {}
        field_description = metadata.get("description", "")
    return template.format(
        field_label=label,
        field_type=ftype,
        field_options=", ".join(str(o) for o in options) if options else "N/A",
        evidence=evidence_text,
        section_name=section_name or "N/A",
        field_description=field_description or "",
    )