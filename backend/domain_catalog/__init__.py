"""Domain catalog: versioned domain manifests + section/field trees.

Each subdirectory holds one domain's ``manifest.json`` (identity) and
``catalog.json`` (full section -> field tree with aliases and intents).
The catalog is the source of truth for the field-alias canonicalization used
by :class:`~backend.ai.mapping.alias_resolver.AliasResolver`.
"""

from .loader import load_catalog, load_manifest, build_upload_payload, available_domains

__all__ = ["load_catalog", "load_manifest", "build_upload_payload", "available_domains"]
