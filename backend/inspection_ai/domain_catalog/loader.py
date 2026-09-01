"""Load domain catalog files from disk and build API upload payloads.

The catalog files live inside the backend package so they can be shipped with
the service and loaded either programmatically (scripts / startup) or through
the ``POST /domains/upload`` endpoint.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

CATALOG_ROOT = Path(__file__).resolve().parent


def load_manifest(domain_slug: str) -> Dict[str, Any]:
    """Read a domain's ``manifest.json`` (identity: name/version/counts)."""
    path = CATALOG_ROOT / domain_slug / "manifest.json"
    if not path.exists():
        raise FileNotFoundError(f"Domain manifest not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_catalog(domain_slug: str) -> List[Dict[str, Any]]:
    """Read a domain's ``catalog.json`` (sections -> fields tree)."""
    path = CATALOG_ROOT / domain_slug / "catalog.json"
    if not path.exists():
        raise FileNotFoundError(f"Domain catalog not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def build_upload_payload(domain_slug: str) -> Dict[str, Any]:
    """Merge manifest identity + catalog tree into the ``POST /domains/upload``
    payload shape.

    This is exactly what Swagger expects for the composite upload endpoint.
    """
    manifest = load_manifest(domain_slug)
    sections = load_catalog(domain_slug)

    for order, section in enumerate(sections):
        section.setdefault("order", order)

    payload = {
        "domain_name": manifest.get("domain_name") or manifest.get("name"),
        "display_name": manifest.get("displayName"),
        "version": manifest.get("version", "1.0.0"),
        "description": manifest.get("description", ""),
        "sections": sections,
    }
    logger.info(
        "[domain_catalog] built upload payload: domain=%s sections=%d fields=%d",
        payload["domain_name"],
        len(payload["sections"]),
        sum(len(s.get("fields", [])) for s in payload["sections"]),
    )
    return payload


def available_domains() -> List[str]:
    """List slugs of every domain catalog bundled with the backend."""
    return sorted(
        p.name for p in CATALOG_ROOT.iterdir() if p.is_dir() and (p / "catalog.json").exists()
    )
