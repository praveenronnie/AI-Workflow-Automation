"""Canonical field resolution based on a domain manifest.

The universal mapper works on ``FormField`` objects whose ``label`` is the
*raw* text scraped from the form.  To get reliable semantic retrieval we map
that raw label (or any of its aliases) onto the canonical field ``name``
stored in the ``domain_fields`` table, and attach the matching
``definition_id`` + ``section_id`` so the vector store can group/filter
results by section.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from inspection_ai.database.models.domain_manifest import DomainField, DomainSection
from inspection_ai.database.models.domain import Domain
from inspection_ai.universal_service.indexer.vector_store import SearchQuery

from sqlalchemy import select
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)


def _normalize_token(text: str) -> str:
    if not text:
        return ""
    return " ".join(text.strip().lower().split())


class AliasResolver:
    def __init__(self, domain_name: str, section_fields: Dict[str, List[DomainField]]):
        self.domain_name = domain_name
        self._by_name: Dict[str, Tuple[str, str, List[str]]] = {}
        self._alias_index: Dict[str, str] = {}
        self._descriptions: Dict[str, str] = {}
        self._build(section_fields)

    def _build(self, section_fields: Dict[str, List[DomainField]]) -> None:
        for _section_id, fields in section_fields.items():
            for f in fields:
                if not f.name:
                    continue
                aliases = list(f.aliases or [])
                alias_tokens = [_normalize_token(a) for a in aliases]
                self._by_name[f.name] = (str(f.id), str(f.section_id), aliases)
                self._alias_index[_normalize_token(f.name)] = f.name
                self._descriptions[f.name] = f.description or ""
                for tok in alias_tokens:
                    if tok:
                        self._alias_index[tok] = f.name

    @classmethod
    def empty(cls, domain_name: str) -> "AliasResolver":
        return cls(domain_name, {})

    def _fuzzy_match(self, raw: str) -> Optional[str]:
        raw_tokens = set(_normalize_token(raw).split())
        if not raw_tokens:
            return None
        best_name: Optional[str] = None
        best_overlap = 0
        for alias_tok, canonical in self._alias_index.items():
            overlap = len(raw_tokens & set(alias_tok.split()))
            if overlap > best_overlap:
                best_overlap = overlap
                best_name = canonical
        if best_overlap > 0:
            return best_name
        return None

    def canonicalize(
        self, raw_label: str
    ) -> Tuple[str, Optional[str], Optional[str], str]:
        if not raw_label:
            return "", None, None, "none"
        norm = _normalize_token(raw_label)
        canonical = self._alias_index.get(norm)
        if canonical:
            defn_id, sec_id, _ = self._by_name[canonical]
            return canonical, defn_id, sec_id, "exact"
        canonical = self._by_name.get(norm) or self._by_name.get(raw_label)
        if canonical:
            defn_id, sec_id, _ = canonical
            return norm, defn_id, sec_id, "exact"
        fuzzy = self._fuzzy_match(raw_label)
        if fuzzy:
            defn_id, sec_id, _ = self._by_name[fuzzy]
            return fuzzy, defn_id, sec_id, "fuzzy"
        return raw_label, None, None, "none"

    def build_query(self, label: str, section_id: str) -> SearchQuery:
        canonical, defn_id, sec_id, _mode = self.canonicalize(label)
        query_text = canonical or label
        return SearchQuery(
            canonical_name=query_text,
            definition_id=defn_id or label,
            section_id=sec_id or section_id,
        )

    def build_queries(self, label: str, section_id: str) -> List[SearchQuery]:
        canonical, defn_id, sec_id, _mode = self.canonicalize(label)
        if not canonical or defn_id is None:
            return [
                SearchQuery(
                    canonical_name=label,
                    definition_id=defn_id if defn_id else (canonical or label),
                    section_id=section_id,
                )
            ]
        stored = self._by_name.get(canonical)
        aliases = list(stored[2]) if stored else []
        terms = [canonical] + [a for a in aliases if a and a != canonical]

        combined_parts = [canonical]
        combined_parts.extend(a for a in aliases if a and a != canonical)
        description = self._descriptions.get(canonical, "")
        if description:
            combined_parts.append(description)
        enriched_text = " ".join(combined_parts)

        target_sec = sec_id or section_id
        queries: List[SearchQuery] = []
        seen = set()
        en = _normalize_token(enriched_text)
        if en:
            seen.add(en)
            queries.append(
                SearchQuery(
                    canonical_name=enriched_text,
                    definition_id=defn_id,
                    section_id=target_sec,
                )
            )
        for t in terms:
            nt = _normalize_token(t)
            if not nt or nt in seen:
                continue
            seen.add(nt)
            queries.append(
                SearchQuery(
                    canonical_name=t,
                    definition_id=defn_id,
                    section_id=target_sec,
                )
            )
        return queries


async def load_alias_resolver(db_session: Any, domain_name) -> AliasResolver:
    try:
        dom_result = await db_session.execute(
            select(Domain).where(Domain.name == domain_name)
        )
        domain = dom_result.scalar_one_or_none()
        if domain is None:
            logger.info(
                "[AliasResolver] domain '%s' not found — using raw labels", domain_name
            )
            return AliasResolver.empty(domain_name)

        sections_result = await db_session.execute(
            select(DomainSection)
            .options(selectinload(DomainSection.fields))
            .where(DomainSection.manifest_id == domain.id)
        )
        sections = sections_result.scalars().unique().all()

        section_fields: Dict[str, List[DomainField]] = {}
        for section in sections:
            section_fields[str(section.id)] = list(section.fields)

        return AliasResolver(domain_name, section_fields)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[AliasResolver] failed to load manifest for '%s': %s — falling back",
            domain_name,
            exc,
        )
        return AliasResolver.empty(domain_name)
