#!/usr/bin/env python
"""
generate_synonyms.py

Read the PCA-Site-Assessment domain manifest (catalog.json),
automatically add a few high-quality synonyms for each field using
spaCy + WordNet, and write the enriched manifest back to the **same** file.

The script is *idempotent*: running it a second time will only add new
synonyms that were not already present, never duplicate entries.

Usage
-----
    python scripts/generate_synonyms.py

Dependencies (install once in your virtualenv)
----------------------------------------------
    pip install spacy
    python -m spacy download en_core_web_sm
    pip install spacy-wordnet tqdm nltk
    python -m nltk.downloader wordnet omw-1.4
"""

import json
import logging
import pathlib
import sys
from typing import Set, List

import spacy
from spacy_wordnet.wordnet_annotator import (  # noqa: F401
    WordnetAnnotator,
)
from tqdm import tqdm

logger = logging.getLogger(__name__)

MANIFEST_PATH = pathlib.Path(
    r"backend/inspection_ai/domain_catalog/pca_site_assessment/temp.json"
)

MAX_NEW_ALIASES = 4
MIN_TOKEN_LEN = 3

nlp = spacy.load("en_core_web_sm")
nlp.add_pipe("spacy_wordnet", after="tagger")


def _clean_candidate(candidate: str) -> str:
    cand = candidate.strip()
    if len(cand) < MIN_TOKEN_LEN:
        return ""
    if all(ch in ".,;:/\\-_" for ch in cand):
        return ""
    return cand


def _wn_synonyms(token) -> Set[str]:
    synonyms: Set[str] = set()
    for syn in token._.wordnet.synsets():
        for lemma in syn.lemma_names():
            if lemma.lower() != token.text.lower():
                synonyms.add(lemma.replace("_", " ").lower())
    return synonyms


def enrich_field(field: dict) -> dict:
    name = field["name"]
    doc = nlp(name)

    tokens = [t for t in doc if t.pos_ in {"NOUN", "PROPN"}]
    base_terms = {
        _clean_candidate(t.lemma_) for t in tokens if _clean_candidate(t.lemma_)
    }
    wn_terms: Set[str] = set()
    for token in tokens:
        wn_terms.update(_wn_synonyms(token))

    all_candidates = base_terms | wn_terms
    existing = set(field.get("aliases", []))
    new_candidates = [c for c in all_candidates if c and c not in existing]
    new_candidates.sort(key=lambda x: (-len(x), x))
    new_to_add = new_candidates[:MAX_NEW_ALIASES]

    merged = sorted(existing.union(new_to_add))
    field["aliases"] = merged

    if not field.get("description"):
        field["description"] = f"A field capturing {name.lower()}."
    return field


def main() -> int:
    try:
        raw = MANIFEST_PATH.read_text(encoding="utf-8")
        manifest: List[dict] = json.loads(raw)
    except Exception as exc:
        print(f"[ERROR] Could not read {MANIFEST_PATH}: {exc}", file=sys.stderr)
        return 1

    for section in tqdm(manifest, desc="Enriching sections"):
        for idx, fld in enumerate(section.get("fields", [])):
            try:
                section["fields"][idx] = enrich_field(fld)
            except Exception as exc:  # noqa: BLE001
                msg = (
                    f"Skipping field '{fld.get('name')}' in section "
                    f"'{section.get('name')}': {exc}"
                )
                logger.warning(msg)
                print(f"[WARN] {msg}")

    backup_path = MANIFEST_PATH.with_suffix(".backup.json")
    backup_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(
        f"[OK] Finished - enriched catalog written to {MANIFEST_PATH}\n"
        f"     Backup of the original file saved as {backup_path}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
