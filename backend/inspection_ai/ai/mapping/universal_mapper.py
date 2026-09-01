import json
import logging
from typing import List, Dict

from ..models.evidence import Evidence
from ..models.form_schema import FormField
from ..storage.cache import RedisCache
from .evidence_pack_builder import EvidencePackBuilder
from .field_matcher import FieldMatcher
from .alias_resolver import AliasResolver
from .pipeline import MappingPipeline
from ..prompts import render_mapping_prompt
from inspection_ai.prompts.image_inspection.image_inspect_prompt import (
    intent_detection_prompt,
)
from inspection_ai.ai.providers.intent_detector import detect_section_intent

logger = logging.getLogger(__name__)


class UniversalMapper:
    def __init__(
        self,
        llm_client,
        vector_store=None,
        reranker=None,
        redis_client=None,
        domain: str = "property_inspection",
        form_type: str = None,
        min_confidence: float = 0.6,
    ):
        self.llm = llm_client
        self.vector_store = vector_store
        self.user_id = None
        self.reranker = reranker
        self.redis = redis_client
        self.domain = domain
        self.form_type = form_type
        self.min_confidence = min_confidence
        self.alias_resolver: AliasResolver = None
        self.pack_builder = EvidencePackBuilder()
        self.field_matcher = FieldMatcher()
        self.indexer = None
        self.evidence: List[Evidence] = []
        self.section_intents: Dict[str, Dict] = {}

    async def get_section_intent(
        self, section_id: str, section_name: str, fields: List, report_id: str = None
    ) -> Dict:
        if section_id in self.section_intents:
            logger.debug(
                "[MAP] Section intent in-memory cache hit: section=%s report_id=%s",
                section_id,
                report_id,
            )
            return self.section_intents[section_id]

        if self.redis:
            try:
                if isinstance(self.redis, RedisCache):
                    field_count = len(fields) if fields else 0
                    cached = self.redis.get_intent(
                        section_id,
                        field_count,
                        report_id=report_id,
                        form_type=self.form_type,
                    )
                    if cached:
                        logger.info(
                            "[MAP] Section intent REDIS cache hit: section=%s report_id=%s",
                            section_id,
                            report_id,
                        )
                        self.section_intents[section_id] = cached
                        return cached
                    logger.info(
                        "[MAP] Section intent REDIS cache miss: section=%s report_id=%s",
                        section_id,
                        report_id,
                    )
            except Exception as e:
                logger.warning(
                    "[MAP] Redis intent get failed: section=%s report_id=%s error=%s",
                    section_id,
                    report_id,
                    e,
                )

        intent = await detect_section_intent(
            section_id=section_id,
            section_name=section_name,
            fields=fields,
            llm_client=self.llm,
        )

        if self.redis and intent:
            try:
                if isinstance(self.redis, RedisCache):
                    field_count = len(fields) if fields else 0
                    self.redis.set_intent(
                        section_id,
                        field_count,
                        intent,
                        ttl=3600,
                        report_id=report_id,
                        form_type=self.form_type,
                    )
                    logger.debug(
                        "[MAP] Section intent stored in REDIS: section=%s report_id=%s",
                        section_id,
                        report_id,
                    )
            except Exception as e:
                logger.warning(
                    "[MAP] Redis intent set failed: section=%s report_id=%s error=%s",
                    section_id,
                    report_id,
                    e,
                )

        if intent:
            self.section_intents[section_id] = intent

        return intent or {}

    async def detect_intent_llm(
        self, section_id: str, section_name: str, fields: List
    ) -> Dict:
        try:
            field_info = []
            for f in fields[:10]:
                field_info.append("- {}: {}".format(f.label, f.type))
            fields_text = "\n".join(field_info)

            prompt = intent_detection_prompt(
                section_id=section_id, section_name=section_name, fields=fields_text
            )

            response = await self.llm.generate_async(
                prompt,
                system="You are a form analysis assistant. Respond only with valid JSON.",
                temperature=0.3,
                flow_type="intent_detection",
            )
            logger.info(
                "[MAP] Intent LLM response received: section=%s response_len=%d",
                section_id,
                len(response) if isinstance(response, str) else 0,
            )

            try:
                intent = json.loads(response)
                if isinstance(intent, dict):
                    logger.info(
                        "[MAP] Intent detection complete: section=%s", section_id
                    )
                    return intent
                logger.warning(
                    "[MAP] Intent LLM returned non-dict: section=%s", section_id
                )
            except json.JSONDecodeError as je:
                logger.warning(
                    "[MAP] Intent response JSON decode failed: section=%s error=%s",
                    section_id,
                    je,
                )
        except Exception as e:
            logger.warning("Intent detection failed: %s", e)

        logger.info("[MAP] Intent detection fallback: section=%s", section_id)
        return {"intent": section_id, "semantic_queries": [section_id]}

    async def map_form(
        self, form_schema, evidence, report_id: str = None, user_id: str = None,
        document_ids: list = None,
    ):
        self.evidence = evidence
        self.user_id = user_id

        section_count = len(getattr(form_schema, "sections", [])) if form_schema else 0
        logger.info(
            "[MAP] map_form started: report_id=%s user_id=%s evidence=%d sections=%d",
            report_id,
            user_id,
            len(evidence),
            section_count,
        )

        result = await MappingPipeline(
            llm_client=self.llm,
            vector_store=self.vector_store,
            reranker=self.reranker,
            alias_resolver=self.alias_resolver,
            indexer=self.indexer,
            intent_fn=self.get_section_intent,
            domain=self.domain,
            min_confidence=self.min_confidence,
        ).map_form(
            form_schema,
            evidence,
            report_id=report_id or "",
            user_id=user_id or "",
            document_ids=document_ids or [],
        )

        logger.info(
            "[MAP] map_form complete: report_id=%s mapped=%d",
            report_id,
            len(result),
        )
        return result

    def resolve_field_evidence(
        self,
        field,
        all_queries,
        query_to_results,
        report_id: str = None,
    ) -> List[Evidence]:
        seen = set()
        merged = []
        for q in all_queries:
            for c in query_to_results.get(q, []):
                cid = c.get("id")
                if cid and cid not in seen:
                    seen.add(cid)
                    merged.append(self.normalize_chunk(c))
        merged = merged or self.keyword_fallback(field)
        all_dict = {self.chunk_key(c): c for c in merged}
        for bc in self.bm25_search(field.label, top_k=50):
            key = self.chunk_key(bc)
            if key not in all_dict:
                all_dict[key] = bc
        merged_final = list(all_dict.values())
        if self.reranker:
            try:
                merged_final = self.reranker.rerank(field.label, merged_final, top_k=15)
            except Exception:
                pass
        return self.chunks_to_evidence(merged_final[:10])

    def map_fields_individually(
        self, fields: List[FormField], packs: List[Dict], section_name: str = ""
    ) -> Dict:
        results = {}
        if not self.llm:
            logger.warning(
                "[MAP] map_fields_individually: no LLM client available, fields=%d",
                len(fields),
            )
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
                    logger.debug(
                        "[MAP] Per-field mapping complete: field_id=%s", field.id
                    )
                else:
                    logger.warning(
                        "[MAP] Per-field mapping non-dict response: field_id=%s",
                        field.id,
                    )
            except Exception as e2:
                logger.warning("Per-field LLM mapping failed: %s", e2)
                logger.warning(
                    "[MAP] Per-field mapping FAILED: field_id=%s error=%s",
                    field.id,
                    e2,
                )
        logger.info(
            "[MAP] map_fields_individually complete: mapped=%d/%d",
            len(results),
            len(fields),
        )
        return results

    @staticmethod
    def chunk_key(chunk):
        if isinstance(chunk, dict):
            return chunk.get("id") or str(chunk.get("content", ""))[:50]
        return chunk.id or chunk.value

    def bm25_search(self, query, top_k=100):
        if self.indexer and getattr(self.indexer, "bm25_index", None):
            return self.indexer.bm25_index.search(query, top_k=top_k)
        tokens = set(self.tokenize(query))
        results = []
        for evt in self.evidence:
            ev_tokens = set(
                self.tokenize(
                    " ".join([evt.field_name, str(evt.value), evt.raw_text or ""])
                )
            )
            if tokens & ev_tokens:
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
        return results[:top_k]

    def chunks_to_evidence(self, chunks):
        return [self.chunk_to_evidence(c) for c in chunks]

    def chunk_to_evidence(self, chunk):
        if self.indexer:
            return self.indexer.chunk_to_evidence(chunk)
        if isinstance(chunk, Evidence):
            return chunk
        meta = chunk.get("metadata", {}) if isinstance(chunk, dict) else {}
        if not isinstance(meta, dict):
            meta = {}
        if isinstance(meta.get("evidence"), Evidence):
            return meta["evidence"]
        return Evidence(
            id=chunk.get("id", "") if isinstance(chunk, dict) else "",
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

    def calc_confidence(self, evidence: List[Evidence]) -> float:
        if not evidence:
            return 0.0
        return sum(e.confidence for e in evidence) / len(evidence)

    def confidence_ok(self, evidence: List[Evidence]) -> bool:
        return self.calc_confidence(evidence) >= self.min_confidence

    def keyword_fallback(self, field: FormField) -> List[Dict]:
        keywords = set(self.tokenize(field.label))
        scored = []
        for evt in self.evidence:
            text = " ".join(
                [evt.field_name or "", str(evt.value or ""), evt.raw_text or ""]
            )
            tokens = set(self.tokenize(text))
            overlap = keywords & tokens
            if overlap:
                scored.append((len(overlap), evt))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [self.evidence_to_chunk(e) for _, e in scored[:5]]

    @staticmethod
    def evidence_to_chunk(evt: Evidence) -> Dict:
        content = f"{evt.field_name}: {evt.value}"
        if evt.raw_text:
            content += f"\nRaw: {evt.raw_text[:200]}"
        return {
            "id": evt.id,
            "content": content,
            "metadata": {
                "confidence": evt.confidence,
                "field_name": evt.field_name,
                "value": evt.value,
                "data_type": evt.data_type,
                "source_type": evt.source_type,
                "source_ref": evt.source_ref,
                "report_id": evt.report_id,
                "evidence": evt,
            },
        }

    @staticmethod
    def normalize_chunk(c: Dict) -> Dict:
        if not c:
            return c
        if c.get("content"):
            return c
        meta = c.get("metadata", {})
        if not isinstance(meta, dict):
            meta = {}
        field_name = meta.get("field_name", "")
        value = meta.get("value")
        raw = meta.get("raw_text") or meta.get("raw")
        if field_name:
            content = f"{field_name}: {value}"
        elif value is not None:
            content = str(value)
        else:
            content = ""
        if raw:
            content = (
                (content + f"\nRaw: {str(raw)[:200]}") if content else str(raw)[:200]
            )
        return {"id": c.get("id"), "content": content, "metadata": meta}

    def set_evidence(self, evidence: List[Evidence]):
        self.evidence = evidence

    def tokenize(self, text: str) -> List[str]:
        if not text:
            return []
        return text.lower().split()
