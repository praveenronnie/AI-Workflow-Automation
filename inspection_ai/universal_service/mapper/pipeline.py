"""Concurrent mapping pipeline — one coroutine per section, alias‑first field matching.

Replaces the sequential section loop inside UniversalMapper.map_form.
Every section runs in parallel, bounded by map_section_concurrency,
and every field inside a section is a single coroutine that bundles alias
resolution → evidence retrieval → rule‑match → LLM fallback.
"""

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from ..models.evidence import Evidence
from ..models.form_schema import FormField, FormSection, UniversalFormSchema
from ..indexer.vector_store import SearchQuery
from ..prompts import render_mapping_prompt
from .alias_resolver import AliasResolver
from .evidence_pack_builder import EvidencePackBuilder
from .field_matcher import FieldMatcher
from .form_schema_adapter import resolve_option_id
from inspection_ai.config import Settings, get_settings

logger = logging.getLogger(__name__)

DEFAULT_DOMAIN = "pca_site_assessment"

RETRY_ATTEMPTS = 3
RETRY_BACKOFF_SEC = 0.5


async def _retry(
    coro_fn,
    *,
    attempts: int = RETRY_ATTEMPTS,
    backoff: float = RETRY_BACKOFF_SEC,
    label: str = "call",
):
    """Run an async callable with a small retry/backoff (transient failures)."""
    last_exc: Optional[Exception] = None
    for attempt in range(1, attempts + 1):
        try:
            return await coro_fn()
        except Exception as exc:  # noqa: BLE001 — retry any transient failure
            last_exc = exc
            if attempt < attempts:
                logger.warning(
                    "[MAP] %s failed (attempt %d/%d): %s — retrying",
                    label,
                    attempt,
                    attempts,
                    exc,
                )
                await asyncio.sleep(backoff * attempt)
    logger.warning("[MAP] %s failed after %d attempts: %s", label, attempts, last_exc)
    return None


class MappingPipeline:
    def __init__(
        self,
        llm_client,
        vector_store=None,
        reranker=None,
        alias_resolver: Optional[AliasResolver] = None,
        indexer=None,
        intent_fn=None,  # Async callable for section-level intent detection
        domain: str = DEFAULT_DOMAIN,
        min_confidence: float = 0.6,
        settings: Optional[Settings] = None,
    ):
        self.llm = llm_client
        self.vector_store = vector_store
        self.reranker = reranker
        self.alias_resolver = alias_resolver or AliasResolver.empty(domain)
        self.indexer = indexer
        self.intent_fn = intent_fn
        self.domain = domain
        self.min_confidence = min_confidence
        self.settings = settings or get_settings()
        self.pack_builder = EvidencePackBuilder()
        self.field_matcher = FieldMatcher()
        # Hybrid retrieval score-fusion weights (configurable via Settings).
        self.vector_weight = getattr(self.settings, "vector_weight", 0.7)
        self.bm25_weight = getattr(self.settings, "bm25_weight", 0.3)
        self.rerank_top_k = getattr(self.settings, "rerank_top_k", 25)
        self.section_sem = asyncio.Semaphore(self.settings.map_section_concurrency)
        self.llm_sem = asyncio.Semaphore(self.settings.max_concurrent_llm_calls)
        # Bounded per-field fan-out for the cheap (retrieval + rule + rerank)
        # work, so a dense section doesn't spike CPU/memory. Defaults to a sane
        # ceiling derived from the LLM pool but is independently configurable.
        self.field_sem = asyncio.Semaphore(
            getattr(self.settings, "max_concurrent_fields_per_report", 32)
        )
        self.evidence: List[Evidence] = []
        self.report_id: str = ""
        self.user_id: str = ""
        # Shared knowledge base: documents linked to the report, used to scope
        # vector retrieval to the report's evidence.
        self.document_ids: Optional[List[str]] = None

    async def map_form(
        self,
        form_schema: UniversalFormSchema,
        evidence: List[Evidence],
        report_id: str = "",
        user_id: str = "",
        document_ids: Optional[List[str]] = None,
    ) -> Dict[str, Dict]:
        """Run the concurrent pipeline — replaces UniversalMapper.map_form."""
        self.evidence = evidence
        self.report_id = report_id
        self.user_id = user_id
        self.document_ids = document_ids or []

        section_count = len(getattr(form_schema, "sections", [])) if form_schema else 0
        logger.info(
            "[MAP] map_form started: report_id=%s user_id=%s evidence=%d sections=%d",
            report_id,
            user_id,
            len(evidence),
            section_count,
        )

        if not form_schema or not form_schema.sections:
            logger.info("[MAP] map_form: no sections to process")
            return {}

        section_tasks = [
            self.process_section(section) for section in form_schema.sections
        ]
        section_results_list = await asyncio.gather(*section_tasks)

        result: Dict[str, Dict] = {}
        for section_res in section_results_list:
            if section_res:
                result.update(section_res)

        # Run-level metrics: how many fields actually got a value, by method.
        by_method: Dict[str, int] = {}
        for v in result.values():
            m = (
                (v.get("mapping_method") or "unknown")
                if isinstance(v, dict)
                else "unknown"
            )
            by_method[m] = by_method.get(m, 0) + 1
        total_fields = sum(len(s.fields) for s in form_schema.sections)
        logger.info(
            "[MAP] map_form complete: report_id=%s total_fields=%d mapped=%d "
            "unmapped=%d by_method=%s",
            report_id,
            total_fields,
            len(result),
            max(0, total_fields - len(result)),
            by_method,
        )
        return result

    async def process_section(self, section: FormSection) -> Dict[str, Dict]:
        """Process one section end‑to‑end (alias → intent → vector → rule → llm)."""
        async with self.section_sem:
            logger.info(
                "[MAP] Section start: id=%s title=%s report_id=%s fields=%d",
                section.id,
                section.title,
                self.report_id,
                len(section.fields),
            )

            # 1 — Alias resolution per field
            alias_results: Dict[str, Tuple[str, Optional[str], Optional[str], str]] = {}
            matched_field_ids: List[str] = []
            fallback_field_ids: List[str] = []

            for field in section.fields:
                canonical, defn_id, sec_id, mode = self.alias_resolver.canonicalize(
                    field.label
                )
                alias_results[field.id] = (canonical, defn_id, sec_id, mode)
                if mode != "none":
                    matched_field_ids.append(field.id)
                else:
                    fallback_field_ids.append(field.id)

            logger.info(
                "[MAP] Alias resolution: section=%s matched=%d fallback=%d",
                section.id,
                len(matched_field_ids),
                len(fallback_field_ids),
            )

            # 2 — Build SearchQuery list: alias queries first
            #    Each matched field issues one query per term — canonical name
            #    PLUS every DB-stored alias — all sharing the same definition_id.
            queries: List[SearchQuery] = []
            for field in section.fields:
                canonical, defn_id, _sec_id, _mode = alias_results[field.id]
                if _mode != "none":
                    queries.extend(
                        self.alias_resolver.build_queries(field.label, section.id)
                    )
                # --- Option-text queries: let each dropdown/radio option act as
                # its own semantic probe so chunks containing the exact option
                # wording are retrieved even when the label alone fails.
                if getattr(field, "options", None):
                    for opt_text in field.options:
                        ot = str(opt_text)
                        if ot.strip():
                            queries.append(
                                SearchQuery(
                                    canonical_name=ot,
                                    definition_id=ot,
                                    section_id=section.id,
                                )
                            )
                # --- Synonym expansion: broaden recall for generic labels.
                for syn in self._field_synonyms(field.label):
                    queries.append(
                        SearchQuery(
                            canonical_name=syn,
                            definition_id=syn,
                            section_id=section.id,
                        )
                    )

            # LLM intent only for unmatched fields
            semantic_queries: List[str] = []
            if fallback_field_ids:
                intent_fn = self.intent_fn or self.get_section_intent
                intent = await _retry(
                    lambda: intent_fn(section.id, section.title, section.fields),
                    attempts=2,
                    label=f"intent detection (section={section.id})",
                )
                semantic_queries = (
                    intent.get("semantic_queries", [])
                    if isinstance(intent, dict)
                    else []
                )

            for sq in semantic_queries:
                queries.append(
                    SearchQuery(
                        canonical_name=sq,
                        definition_id=sq,
                        section_id=section.id,
                    )
                )

            logger.info(
                "[MAP] Total queries: section=%s count=%d (alias=%d semantic=%d)",
                section.id,
                len(queries),
                len(matched_field_ids),
                len(semantic_queries),
            )

            # 3 — Vector batch search (retry-wrapped; consumed as by_field DICT)
            by_field: Dict[str, Any] = {}
            if queries and self.vector_store and self.vector_store.client:
                vector_resp = await _retry(
                    lambda: self.vector_store.search_batch(
                        queries,
                        top_k=40,
                        report_id=self.report_id,
                        document_ids=self.document_ids or None,
                        user_id=self.user_id,
                    ),
                    label=f"vector search (section={section.id})",
                )
                if isinstance(vector_resp, dict):
                    by_field = vector_resp.get("by_field", {})
                logger.info(
                    "[MAP] Vector search: section=%s query_count=%d by_field_keys=%d",
                    section.id,
                    len(queries),
                    len(by_field),
                )

            # 4 — Per‑field concurrent resolution (single unit per field)
            # Aggregate semantic-query matches so fallback fields can still use them.
            semantic_matches: List[Any] = []
            if isinstance(by_field, dict):
                for sq in semantic_queries:
                    if not sq:
                        continue
                    sem_entry = by_field.get(sq) or {}
                    if isinstance(sem_entry, dict):
                        semantic_matches.extend(sem_entry.get("matches", []))
            logger.info(
                "[MAP] Semantic results: section=%s semantic_queries=%d semantic_matches=%d",
                section.id,
                len(semantic_queries),
                len(semantic_matches),
            )

            async def _bounded_field(f):
                # Bound the cheap per-field work (retrieval + rule + rerank) so a
                # dense section doesn't fan out unbounded coroutines.
                async with self.field_sem:
                    return await self.process_field(
                        f, alias_results, by_field, queries, semantic_matches
                    )

            field_tasks = [_bounded_field(f) for f in section.fields]
            field_outcomes = await asyncio.gather(*field_tasks)

            # Sort outcomes: rule‑matched vs LLM‑needed
            field_evidence: Dict[str, List[Evidence]] = {}
            rule_assignments: Dict[str, Dict] = {}
            llm_fields: List[FormField] = []
            llm_packs: List[Dict] = []

            for field, evs, rule_result, llm_field, pack in field_outcomes:
                field_evidence[field.id] = evs
                if rule_result is not None:
                    rule_assignments[field.id] = rule_result
                elif llm_field is not None:
                    llm_fields.append(llm_field)
                    llm_packs.append(pack)
            logger.info(
                "[MAP] Section '%s': fields=%d rule_matched=%d llm_needed=%d",
                section.id,
                len(section.fields),
                len(rule_assignments),
                len(llm_fields),
            )

            # 5 — LLM mapping for remaining fields. The section's LLM-needing
            # fields are chunked and dispatched concurrently; each chunk acquires
            # `llm_sem` individually so the GLOBAL in-flight LLM-call count stays
            # bounded by max_concurrent_llm_calls. This lets a large section run
            # its batches in parallel without monopolizing the semaphore.
            llm_results: Dict[str, Dict] = {}
            if llm_fields:
                batch_size = getattr(self.settings, "llm_field_mapping_batch_size", 10)

                async def _dispatch_chunk(cfields, cpacks):
                    async with self.llm_sem:
                        result = await _retry(
                            lambda: self.llm.batch_map_fields_async(
                                cfields,
                                cpacks,
                                flow_type="field_mapping",
                                section_name=section.title,
                            ),
                            label=f"batch LLM mapping (section={section.id})",
                        )
                    return self._flatten_llm_results(result)

                llm_chunks = [
                    (llm_fields[i : i + batch_size], llm_packs[i : i + batch_size])
                    for i in range(0, len(llm_fields), batch_size)
                ]
                llm_lists = await asyncio.gather(
                    *[_dispatch_chunk(cf, cp) for cf, cp in llm_chunks]
                )
                for chunk_map in llm_lists:
                    llm_results.update(chunk_map)
                if not llm_results:
                    llm_results = self.map_fields_individually(
                        llm_fields, llm_packs, section_name=section.title
                    )

            # Build a SECTION-level "fact pool" from the combined evidence of
            # every field in the section, so placeholder-bearing values can be
            # filled even when the number/direction lives in a sibling field's
            # evidence (e.g. "Number of gates: 5" elsewhere in the section).
            section_pool = self._build_section_fact_pool(
                [e for evs in field_evidence.values() for e in evs]
            )

            # 6 — Build section result dict
            section_result: Dict[str, Dict] = {}
            for field in section.fields:
                value = None
                confidence = 0.0
                reasoning = ""
                sources: List[str] = []
                mapping_method = "none"

                if field.id in rule_assignments:
                    rr = rule_assignments[field.id]
                    value = rr.get("value")
                    confidence = rr.get("confidence", 0.0)
                    reasoning = rr.get("reasoning", "")
                    sources = rr.get("sources", [])
                    mapping_method = rr.get("mapping_method", "rule")
                elif field.id in llm_results:
                    lr = llm_results[field.id]
                    value = lr.get("value")
                    confidence = lr.get("confidence", 0.0)
                    reasoning = lr.get("reasoning", "")
                    sources = lr.get("sources", [])
                    mapping_method = "llm"

                if value is None and field.id in matched_field_ids:
                    mapping_method = "manifest"

                if value is not None:
                    evs = field_evidence.get(field.id, [])
                    # Resolve XXXX / XX / [direction] style placeholders using
                    # the section-level fact pool with semantic slot matching —
                    # a "[direction]" slot consumes a direction word and a
                    # "XXXX" slot consumes a number whose context matches the
                    # value's own noun (e.g. "XXXX gates" ← number near "gate").
                    value = self._fill_placeholders(
                        value, evs, field_label=field.label, pool=section_pool
                    )
                    # Structured, traceable sources: every entry carries the
                    # provenance identifiers (source_type + image id / pdf page
                    # name in `ref`, plus file_id, document_id and report_id).
                    sources = self._build_sources(sources, evs)
                    section_result[field.id] = {
                        "value": value,
                        "confidence": confidence or self.calc_confidence(evs),
                        "reasoning": reasoning,
                        "sources": sources,
                        "mapping_method": mapping_method,
                        "evidence": [e.model_dump() for e in evs[:3]],
                    }

            # Section metrics: matched vs unmatched breakdown
            rule_count = sum(1 for f in section.fields if f.id in rule_assignments)
            llm_count = sum(1 for f in section.fields if f.id in llm_results)
            filled = len(section_result)
            unmatched = [f.label for f in section.fields if f.id not in section_result]
            logger.info(
                "[MAP] Section done: id=%s fields=%d matched=%d "
                "(rule=%d llm=%d) unmatched=%d",
                section.id,
                len(section.fields),
                filled,
                rule_count,
                llm_count,
                len(unmatched),
            )
            if unmatched:
                logger.info(
                    "[MAP] Section '%s' UNMATCHED (%d): %s",
                    section.id,
                    len(unmatched),
                    unmatched[:10],
                )
            return section_result

    async def process_field(
        self,
        field: FormField,
        alias_results: Dict[str, Tuple[str, Optional[str], Optional[str], str]],
        by_field: Dict[str, Any],
        queries: List[SearchQuery],
        semantic_matches: Optional[List[Any]] = None,
    ) -> Tuple[
        FormField, List[Evidence], Optional[Dict], Optional[FormField], Optional[Dict]
    ]:
        """Single‑unit coroutine: evidence → rule‑match → pack."""
        canonical, defn_id, _sec_id, mode = alias_results[field.id]

        entry = by_field.get(defn_id) or by_field.get(canonical) or {}
        matches = entry.get("matches", []) if isinstance(entry, dict) else []
        # Hits returned under option-text / synonym probes belong to this field.
        if isinstance(by_field, dict):
            seen_ids = set()
            for m in matches:
                mid = m.get("id") if isinstance(m, dict) else getattr(m, "id", None)
                # Guard: payload ids may occasionally be nested dicts, which
                # are unhashable — fall back to the stable chunk_key().
                if not isinstance(mid, (str, int)):
                    mid = self.chunk_key(m)
                if mid:
                    seen_ids.add(mid)
            extra_terms = [str(o) for o in (getattr(field, "options", None) or [])]
            extra_terms += self._field_synonyms(field.label)
            for term in extra_terms:
                t_entry = by_field.get(term) or {}
                if not isinstance(t_entry, dict):
                    continue
                for m in t_entry.get("matches", []): 
                    mid = m.get("id") if isinstance(m, dict) else getattr(m, "id", None)
                    if not isinstance(mid, (str, int)):
                        mid = self.chunk_key(m)
                    if mid and mid in seen_ids:
                        continue
                    if mid:
                        seen_ids.add(mid)
                    matches.append(m)
        if mode == "none":
            matches = list(matches) + list(semantic_matches or [])

        merged = self.resolve_field_evidence(
            field,
            [q.canonical_name for q in queries],
            {q.canonical_name: matches for q in queries if q.canonical_name},
            report_id=self.report_id,
        )

        if not merged:
            # No retrieval hit at all — still give the LLM a chance with an
            # (empty) pack instead of silently dropping the field.
            try:
                pack = self.pack_builder.build(field, [])
            except Exception:
                pack = {}
            logger.info(
                "[MAP] Field '%s' (%s): no evidence retrieved — LLM fallback",
                field.label,
                field.id,
            )
            return field, [], None, field, pack

        rule_result = self.field_matcher.match_evidence(field, merged)
        if (
            rule_result is not None
            and rule_result.get("confidence", 0.0) >= self.min_confidence
        ):
            # A rule match is only trustworthy for optioned (dropdown/radio/
            # multi_select) fields when it actually resolves to one of the
            # defined options. If the rule picked some unrelated text, route the
            # field to the LLM so a legitimate option is chosen instead of
            # auto-populating garbage.
            if self._rule_value_resolves_to_option(field, rule_result.get("value")):
                rule_result.setdefault("mapping_method", "rule")
                return field, merged, rule_result, None, None
            logger.info(
                "[MAP] Field '%s' (%s): rule value %r not mappable to an option — "
                "sending to LLM",
                field.label,
                field.id,
                rule_result.get("value"),
            )

        try:
            pack = self.pack_builder.build(field, merged)
        except Exception as exc:
            logger.warning(
                "[MAP] pack_builder failed: field_id=%s error=%s",
                field.id,
                exc,
                exc_info=True,
            )
            pack = {}

        return field, merged, None, field, pack

    @staticmethod
    def _flatten_llm_results(result) -> Dict[str, Dict]:
        """Turn the LLM batch result (a list of dicts or a single dict) into a
        ``{field_id: result}`` map."""
        flattened: Dict[str, Dict] = {}
        if isinstance(result, dict):
            # Single dict: either direct {field_id: ...} or {'fields': {...}}.
            nested = result.get("fields")
            if isinstance(nested, dict):
                return {str(k): v for k, v in nested.items()}
            for k, v in result.items():
                if isinstance(v, dict):
                    flattened[str(k)] = v
            return flattened
        if isinstance(result, list):
            for res in result:
                if isinstance(res, dict):
                    fid = res.get("field_id")
                    if fid:
                        flattened[str(fid)] = res
        return flattened

    def _rule_value_resolves_to_option(self, field: FormField, value) -> bool:
        """True only if ``value`` maps to one of the field's defined options.

        Non-optioned (text/number) fields always return ``True`` so the rule
        matcher is allowed to skip the LLM. For optioned fields the value must
        resolve to a real ``option_id``; otherwise the rule is wrong-matching and
        the caller should route the field to the LLM.
        """
        if getattr(field, "options", None) is None:
            return True
        metadata = getattr(field, "metadata", None) or {}

        # Prefer the preserved {id: text} dict stored by field_from_dict.
        options_dict = metadata.get("options_dict")
        if not options_dict:
            # OpenQuire fields store the raw dict under metadata["original"].
            original = metadata.get("original") or {}
            options_dict = (
                original.get("options") if isinstance(original, dict) else None
            )
        if not options_dict:
            # Last resort: synthesize deterministic ids from the option list.
            options_dict = {str(i): str(o) for i, o in enumerate(field.options or [])}

        meta = {
            "options": options_dict,
            "options_map": metadata.get("options_map", {}) or {},
            "options_map_exact": metadata.get("options_map_exact", {}) or {},
        }
        _resolved, option_id = resolve_option_id(meta, value)
        return option_id is not None

    async def get_section_intent(
        self, section_id: str, section_name: str, fields: List[FormField]
    ) -> Dict:
        """LLM intent detection for fallback semantic queries (no caching)."""
        try:
            from inspection_ai.services.intent_detector import detect_section_intent

            intent = await detect_section_intent(
                section_id=section_id,
                section_name=section_name,
                fields=fields,
                llm_client=self.llm,
            )
            return intent or {}
        except Exception as exc:
            logger.warning(
                "[MAP] intent detection failed: section=%s error=%s",
                section_id,
                exc,
                exc_info=True,
            )
        return {"intent": section_id, "semantic_queries": [section_id]}

    def map_fields_individually(
        self, fields: List[FormField], packs: List[Dict], section_name: str = ""
    ) -> Dict[str, Dict]:
        """Per‑field LLM fallback (synchronous)."""
        results: Dict[str, Dict] = {}
        if not self.llm:
            return results
        for field, pack in zip(fields, packs):
            try:
                prompt = render_mapping_prompt(
                    self.domain, field, pack, section_name=section_name
                )
                response = self.llm.generate(
                    prompt, temperature=0.1, flow_type="field_mapping"
                )
                parsed = json.loads(response) if response else {}
                if isinstance(parsed, dict):
                    results[field.id] = parsed
            except Exception as exc:
                logger.warning(
                    "[MAP] Individual field LLM failed: field_id=%s error=%s",
                    field.id,
                    exc,
                    exc_info=True,
                )
        return results

    def resolve_field_evidence(
        self,
        field: FormField,
        all_queries: List[str],
        query_to_results: Dict[str, List],
        report_id: str = "",
    ) -> List[Evidence]:
        """Merge vector matches + BM25 fallback + rerank → list of Evidence.

        Score fusion (vector similarity ↔ BM25) is applied **before** the
        cross‑encoder reranker so the reranker always sees a balanced,
        hybrid‑ranked candidate list.
        """
        seen = set()
        merged: List[Any] = []
        for q in all_queries:
            for c in query_to_results.get(q, []):
                cid = c.get("id") if isinstance(c, dict) else None
                # Guard against unhashable (dict) payload ids.
                if not isinstance(cid, (str, int)):
                    cid = self.chunk_key(c)
                if cid and cid not in seen:
                    seen.add(cid)
                    # shallow copy so we can attach scoring metadata without
                    # mutating the vector-store response
                    if isinstance(c, dict):
                        c = dict(c)
                        c.setdefault("score_src", "vector")
                    merged.append(self.normalize_chunk(c))

        merged = merged or self.keyword_fallback(field)
        all_dict = {self.chunk_key(c): c for c in merged}
        for bc in self.bm25_search(field.label, top_k=50):
            key = self.chunk_key(bc)
            if key not in all_dict:
                all_dict[key] = bc

        # ---------------------------------------------------------------
        # 1️⃣ Hybrid score fusion: vector similarity ↔ BM25
        # ---------------------------------------------------------------
        max_vec = (
            max(
                (self._extract_score(c, "vector") for c in all_dict.values()),
                default=1.0,
            )
            or 1.0
        )
        max_bm25 = (
            max(
                (self._extract_score(c, "bm25") for c in all_dict.values()),
                default=1.0,
            )
            or 1.0
        )

        for c in all_dict.values():
            vec_norm = self._extract_score(c, "vector") / max_vec
            bm25_norm = self._extract_score(c, "bm25") / max_bm25
            c["fused_score"] = (
                self.vector_weight * vec_norm + self.bm25_weight * bm25_norm
            )

        merged_final = list(all_dict.values())
        merged_final.sort(key=lambda x: x.get("fused_score", 0), reverse=True)

        # ---------------------------------------------------------------
        # 2️⃣ Cross-encoder rerank on the fused list
        # ---------------------------------------------------------------
        rerank_query = field.label or ""
        if self.reranker:
            try:
                merged_final = self.reranker.rerank(
                    rerank_query, merged_final, top_k=self.rerank_top_k
                )
            except Exception as exc:
                logger.debug(
                    "[MAP] reranker skipped: field=%s error=%s",
                    field.id,
                    exc,
                )

        # ---------------------------------------------------------------
        # 3️⃣ Lexical-overlap boost (final tie-breaker)
        # ---------------------------------------------------------------
        scored = [(self._lexical_score(field, c), c) for c in merged_final]
        scored.sort(key=lambda x: x[0], reverse=True)
        merged_final = [c for _, c in scored]
        return self.chunks_to_evidence(merged_final[:10])

    # ------------------------------------------------------------------
    # Helpers for the hybrid step
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_score(chunk: Any, src: str) -> float:
        """Return the raw score for a chunk from *src*.

        ``src`` is either ``'vector'`` or ``'bm25'``.
        Returns 0.0 when no score is present.
        """
        if not isinstance(chunk, dict):
            return 0.0
        meta = chunk.get("metadata") or {}
        if src == "vector":
            return float(chunk.get("score", meta.get("score", 0.0)) or 0.0)
        if src == "bm25":
            return float(meta.get("bm25_score", 0.0) or 0.0)
        return 0.0

    @staticmethod
    def _lexical_score(field: FormField, chunk: Any) -> float:
        """Token-overlap boost between the field label and the chunk text."""
        label_tokens = {
            t
            for t in re.findall(r"[a-z0-9]+", (field.label or "").lower())
            if len(t) > 2
        }
        if not label_tokens:
            return 0.0
        meta = chunk.get("metadata") if isinstance(chunk, dict) else None
        meta = meta if isinstance(meta, dict) else {}
        text = " ".join(
            str(x or "")
            for x in (
                meta.get("text"),
                meta.get("field_name"),
                meta.get("value"),
                meta.get("category"),
            )
        ).lower()
        chunk_tokens = {t for t in re.findall(r"[a-z0-9]+", text) if len(t) > 2}
        if not chunk_tokens:
            return 0.0
        return len(label_tokens & chunk_tokens) / len(label_tokens)

    def keyword_fallback(self, field: FormField) -> List[Dict]:
        """Simple substring match across all evidence."""
        results = []
        label_lower = (field.label or "").lower()
        for evt in self.evidence:
            if (
                label_lower in (evt.field_name or "").lower()
                or label_lower in (str(evt.value) or "").lower()
            ):
                results.append(
                    {
                        "id": evt.id,
                        "content": evt.field_name + ": " + str(evt.value),
                        "metadata": {
                            "confidence": evt.confidence,
                            "field_name": evt.field_name,
                            "value": evt.value,
                            "source_type": evt.source_type,
                            "source_ref": evt.source_ref,
                            "report_id": evt.report_id,
                            "evidence": evt,
                        },
                    }
                )
        return results

    def bm25_search(self, query: str, top_k: int = 100) -> List[Dict]:
        """BM25 lookup via indexer or simple token‑overlap fallback."""
        if self.indexer and getattr(self.indexer, "bm25_index", None):
            return self.indexer.bm25_index.search(query, top_k=top_k)
        tokens = set((query or "").lower().split())
        results = []
        for evt in self.evidence:
            ev_tokens = set(
                " ".join(
                    [evt.field_name or "", str(evt.value or ""), evt.raw_text or ""]
                )
                .lower()
                .split()
            )
            if tokens & ev_tokens:
                results.append(
                    {
                        "id": evt.id,
                        "content": f"{evt.field_name}: {evt.value}",
                        "metadata": {
                            "confidence": evt.confidence,
                            "field_name": evt.field_name,
                            "value": evt.value,
                            "source_type": evt.source_type,
                            "source_ref": evt.source_ref,
                            "report_id": evt.report_id,
                            "evidence": evt,
                        },
                    }
                )
        return results[:top_k]

    # ------------------------------------------------------------------
    # Synonym / placeholder / source-traceability helpers
    # ------------------------------------------------------------------

    FIELD_SYNONYMS: Dict[str, List[str]] = {
        "Signage": ["sign", "signage", "monument", "pylon", "building-mounted"],
    }

    @classmethod
    def _field_synonyms(cls, field_label: str) -> List[str]:
        """Return curated synonyms for a field label (empty list by default).

        Extending this map is the lightweight path to improving recall for
        generic UI labels whose source data uses richer phrasing.
        """
        return cls.FIELD_SYNONYMS.get((field_label or "").strip(), [])

    PLACEHOLDER_RE = re.compile(r"X{2,4}|\[[^\]]+\]")

    DIRECTION_WORDS = [
        "northwest",
        "northeast",
        "southeast",
        "southwest",
        "north",
        "south",
        "east",
        "west",
    ]

    NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?\b")

    @classmethod
    def _build_section_fact_pool(cls, evidence: List[Evidence]) -> Dict[str, List]:
        """Build a section-level fact pool of numbers and directions.

        Returns ``{"numbers": [..., {"value": "5", "context": "5 gates broken"}],
        "directions": ["north", "south"]}``. Each number is tagged with the
        tokens that co-occur with it in its context text so a ``XXXX`` slot can
        be filled from a semantically-relevant number (e.g. a slot in an option
        that mentions "gates" prefers a number found near the word "gate").
        """
        numbers: List[Dict[str, str]] = []
        directions: List[str] = []
        seen_nums = set()
        seen_dirs = set()

        for evt in evidence:
            raw = evt.value if isinstance(evt.value, str) else ""
            text = f"{raw} {evt.raw_text or ''}".lower()
            # Direction words first (contextual hints are cheap)
            for d in cls.DIRECTION_WORDS:
                if d in seen_dirs:
                    continue
                if re.search(rf"\b{re.escape(d)}\b", text):
                    directions.append(d)
                    seen_dirs.add(d)
            # Numbers with their surrounding context (for noun matching)
            for m in cls.NUMBER_RE.finditer(text):
                num = m.group(0)
                key = (num, m.start())
                if key in seen_nums:
                    continue
                seen_nums.add(key)
                # A small window around the number gives the noun context
                ctx = text[max(0, m.start() - 40) : min(len(text), m.end() + 40)]
                numbers.append({"value": num, "context": ctx})

        return {"numbers": numbers, "directions": directions}

    @staticmethod
    def _noun_tokens(label: str) -> set:
        """Lowercased content words of a label/value, for noun matching."""
        if not label:
            return set()
        tokens = set(re.findall(r"[a-z][a-z]{1,}", label.lower()))
        # Drop tiny/stop-ish words so "XXXX gates" matches on "gates"
        tokens.discard("the")
        tokens.discard("of")
        tokens.discard("on")
        tokens.discard("in")
        return tokens

    @classmethod
    def _best_number(cls, numbers: List[Dict[str, str]], claim_tokens: set) -> Optional[str]:
        """Pick the number whose context shares the most tokens with the value's
        nouns (e.g. "XXXX gates" matches a number co-occurring with 'gate').
        Falls back to the first number in evidence order."""
        if not numbers:
            return None
        best = None
        best_score = -1
        first = numbers[0]["value"]
        for num in numbers:
            ctx_tokens = set(re.findall(r"[a-z][a-z]{1,}", num["context"]))
            overlap = len(claim_tokens & ctx_tokens)
            if overlap > best_score:
                best_score = overlap
                best = num["value"]
        # Prefer a semantically-matched number; otherwise positional fallback
        return best if best_score > 0 else first

    @classmethod
    def _fill_placeholders(
        cls,
        value: Any,
        evidence: List[Evidence],
        field_label: str = "",
        pool: Dict[str, List] = None,
    ) -> Any:
        """Replace ``XXXX``/``XX`` with numbers and ``[direction]`` tokens with
        compass directions.

        Unlike the naive per-field scan, this uses the SECTION-level fact pool
        (``pool``) so values can be filled from numbers/directions that live in
        sibling fields' evidence. ``XXXX``/``XX`` slots are filled with a number
        whose context matches the value's own nouns when possible (semantic),
        else positionally; ``[direction]`` slots consume compass words. Tokens
        with no candidate stay unchanged.
        """
        if not isinstance(value, str):
            return value
        if not cls.PLACEHOLDER_RE.search(value):
            return value

        numbers: List[Dict[str, str]] = list(pool.get("numbers") or [])
        directions: List[str] = list(pool.get("directions") or [])

        # Semantic anchor: nouns in the option text (e.g. "XXXX gates" -> gates)
        claim_tokens = cls._noun_tokens(value)

        # persist per-value consumed indexes
        state = {"num_idx": 0, "dir_idx": 0}

        def _sub(match: "re.Match[str]") -> str:
            token = match.group(0)
            if token.startswith("["):
                d = directions[state["dir_idx"]] if state["dir_idx"] < len(directions) else token
                if d != token:
                    state["dir_idx"] += 1
                return d
            # XXXX / XX -> number (semantic if nouns match, else positional)
            if numbers:
                n = cls._best_number(numbers, claim_tokens)
                # consume the chosen number from the working copy (deterministic)
                numbers[:] = [x for x in numbers if x["value"] != n]
                return n
            return token

        return cls.PLACEHOLDER_RE.sub(_sub, value)

    MAX_SOURCES_PER_FIELD = 10

    @classmethod
    def _build_sources(
        cls, existing: Optional[List[Any]], evidence: List[Evidence]
    ) -> List[Dict[str, Any]]:
        """Build a de-duplicated, traceable ``sources`` list.

        Every entry contains the unique provenance identifier for its origin:
        * image evidence -> ``ref`` holds the image/file id (``source_ref``),
        * pdf evidence   -> ``ref`` holds the page/document reference,
        plus ``file_id``, ``report_id`` and ``source_type`` for auditing.
        Evidence-derived entries are appended after any rule/LLM-provided ones
        so existing consumers keep working while gaining traceability.
        """
        out: List[Dict[str, Any]] = []
        seen = set()

        def _push(entry: Any) -> None:
            if isinstance(entry, str):
                rec = {"type": "unknown", "ref": entry}
            elif isinstance(entry, dict):
                # Coerce to str so composite keys are always hashable.
                rec = {
                    "type": str(entry.get("type") or entry.get("source_type") or "unknown"),
                    "ref": str(entry.get("ref") or entry.get("source_ref") or ""),
                }
                for k in ("file_id", "report_id", "document_id"):
                    if entry.get(k):
                        rec[k] = str(entry[k])
            else:
                return
            key = (rec["type"], rec["ref"])
            if rec["ref"] and key not in seen:
                seen.add(key)
                out.append(rec)

        for item in existing or []:
            _push(item)
        for evt in evidence:
            _push(
                {
                    "type": evt.source_type,
                    "ref": evt.source_ref,
                    "file_id": evt.file_id,
                    "document_id": evt.document_id,
                    "report_id": evt.report_id,
                }
            )
        return out[: cls.MAX_SOURCES_PER_FIELD]

    def chunks_to_evidence(self, chunks: List[Any]) -> List[Evidence]:
        return [self.chunk_to_evidence(c) for c in chunks]

    def chunk_to_evidence(self, chunk: Any) -> Evidence:
        if self.indexer:
            return self.indexer.chunk_to_evidence(chunk)
        if isinstance(chunk, Evidence):
            return chunk
        meta = chunk.get("metadata", {}) if isinstance(chunk, dict) else {}
        if not isinstance(meta, dict):
            meta = {}
        if isinstance(meta.get("evidence"), Evidence):
            return meta["evidence"]
        cid = chunk.get("id", "") if isinstance(chunk, dict) else ""
        if not isinstance(cid, str):
            # Payload ids may be nested dicts — coerce to a stable string.
            cid = self.chunk_key(chunk)
        if not isinstance(meta.get("field_name"), str):
            meta["field_name"] = str(meta.get("field_name") or "")
        if not isinstance(meta.get("source_type"), str):
            meta["source_type"] = str(meta.get("source_type") or "")
        if not isinstance(meta.get("source_ref"), str):
            meta["source_ref"] = str(meta.get("source_ref") or "")
        if not isinstance(meta.get("report_id"), str):
            meta["report_id"] = str(meta.get("report_id") or "")
        return Evidence(
            id=cid,
            evidence_batch_id="",
            session_id="",
            report_id=meta.get("report_id", ""),
            source_type=meta.get("source_type", ""),
            source_ref=meta.get("source_ref", ""),
            field_name=meta.get("field_name", ""),
            value=meta.get("value", ""),
            data_type=meta.get("data_type", "string"),
            confidence=meta.get("confidence", 0.0),
        )

    @staticmethod
    def chunk_key(chunk: Any) -> str:
        """Stable, always-hashable dedup key for a chunk/match.

        Guards against payloads whose ``id`` was stored as a nested dict
        (which would otherwise raise ``TypeError: unhashable type: 'dict'``
        when used as a set member or dict key).
        """
        if isinstance(chunk, dict):
            cid = chunk.get("id")
            if isinstance(cid, (str, int)) and cid != "":
                return cid
            content = chunk.get("content", "")
            if content:
                return str(content)[:50]
            return json.dumps(chunk, sort_keys=True, default=str)[:80]
        cid = getattr(chunk, "id", None)
        if isinstance(cid, (str, int)) and cid != "":
            return cid
        return str(getattr(chunk, "value", "") or "")[:50]

    @staticmethod
    def calc_confidence(evidence: List[Evidence]) -> float:
        if not evidence:
            return 0.0
        return sum(e.confidence for e in evidence) / len(evidence)

    @staticmethod
    def normalize_chunk(chunk: Any) -> Dict:
        if isinstance(chunk, dict):
            if not chunk.get("content"):
                meta = chunk.get("metadata") or {}
                if isinstance(meta, dict):
                    parts = [
                        str(x)
                        for x in (
                            meta.get("field_name"),
                            meta.get("value"),
                            meta.get("text"),
                        )
                        if x
                    ]
                    chunk["content"] = " | ".join(parts)
            return chunk
        return {"id": getattr(chunk, "id", ""), "content": str(chunk)}
