import logging
from typing import Dict, Any, List

from ..mapper.universal_mapper import UniversalMapper
from ..mapper.form_schema_adapter import normalize_form_schema, resolve_option_id
from ..storage.evidence_store import EvidenceStore
from ..storage.report_registry import ReportRegistry

logger = logging.getLogger(__name__)

# Lowered from 0.8/0.55: previously correct rule/LLM matches landing in the
# 0.3–0.54 band were discarded (e.g. "Waste Enclosures" → "Vinyl fence" at 0.65)
# and many dropdown values never reached the LLM because the rule score was
# just below 0.55. 0.30 ensures that any field with a reasonable textual hit is
# still sent to the LLM so an `option_id` can be resolved.
CONFIDENCE_AUTO_POPULATE = 0.30


class MappingHandler:
    def __init__(
        self,
        mapper: UniversalMapper,
        evidence_store: EvidenceStore = None,
        registry: ReportRegistry = None,
    ):
        self.mapper = mapper
        self.evidence_store = evidence_store
        self.registry = registry

    async def map_form_fields(
        self, report_id: str, form_schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        logger.info(
            "[MAP] MappingHandler.map_form_fields started: report_id=%s", report_id
        )
        if self.registry is not None:
            context = self.registry.get_context(report_id)
            if not context:
                logger.error(
                    "[MAP] MappingHandler: report context not found: report_id=%s",
                    report_id,
                )
                raise ValueError("Report " + report_id + " not found")
            session_id = context.session_id
        else:
            session_id = ""

        if self.evidence_store is not None:
            evidence = self.evidence_store.get_evidence(report_id)
            logger.info(
                "[MAP] Evidence loaded from store: report_id=%s evidence=%d",
                report_id,
                len(evidence),
            )
        else:
            evidence = []
            logger.info("[MAP] No evidence store configured: report_id=%s", report_id)

        schema, field_meta = normalize_form_schema(form_schema)
        logger.info(
            "[MAP] Form schema normalized: report_id=%s fields=%d",
            report_id,
            len(field_meta),
        )
        raw_results = await self.mapper.map_form(
            schema,
            evidence,
            report_id=report_id,
            user_id=getattr(self.mapper, "user_id", None),
        )
        logger.info(
            "[MAP] Mapper produced raw results: report_id=%s mapped=%d",
            report_id,
            len(raw_results),
        )
        results, populated = self.build_results(
            raw_results, field_meta, form_schema, evidence
        )
        logger.info(
            "[MAP] build_results done: report_id=%s results=%d", report_id, len(results)
        )
        logger.info(
            "[MAP] MappingHandler.map_form_fields complete (before return): report_id=%s",
            report_id,
        )

        return {
            "report_id": report_id,
            "session_id": session_id,
            "mappings": results,
            "populated_schema": populated,
        }

    def build_results(
        self,
        raw_results: Dict[str, Dict],
        field_meta: Dict[str, Dict],
        form_schema: Dict[str, Any],
        evidence: List,
    ) -> tuple:
        results: List[Dict[str, Any]] = []
        populated = {k: v for k, v in form_schema.items()}
        logger.info(
            "[MAP] build_results started: raw=%d evidence=%d",
            len(raw_results),
            len(evidence),
        )
        evidence_by_ref = {e.source_ref: e for e in evidence}

        containers = self.collect_containers(form_schema)
        populated_containers = []

        for container in containers:
            container_id = str(container.get("tableId") or container.get("id") or "")
            section_name = container.get("tableName") or container.get("title") or ""
            new_container = {k: v for k, v in container.items()}
            new_fields = []

            for field in container.get("fields", []):
                field_name = (
                    field.get("fieldName")
                    or field.get("label")
                    or field.get("id")
                    or ""
                )
                if not field_name:
                    new_fields.append({k: v for k, v in field.items()})
                    continue

                fid = str(field.get("rowId") or field.get("id") or field_name)
                raw = raw_results.get(fid) or raw_results.get(field_name) or {}

                value = raw.get("value")
                confidence = float(raw.get("confidence", 0.0))
                option_id = None

                meta = field_meta.get(fid, {})
                options = field.get("options") or {}
                optioned = bool(options and value is not None)
                if options and value is not None:
                    value, option_id = resolve_option_id(
                        {
                            "options": options,
                            "options_map": meta.get("options_map", {}),
                            "options_map_exact": meta.get("options_map_exact", {}),
                        },
                        value,
                    )

                # An optioned field only counts as matched when it resolved a real
                # option_id. If the (rule/LLM) value cannot be mapped to an option,
                # leave it unmatched so it can be re-mapped or flagged for review
                # instead of being silently recorded as populated.
                matched = (
                    confidence >= CONFIDENCE_AUTO_POPULATE
                    and value is not None
                    and (not optioned or option_id is not None)
                )

                sources = raw.get("sources", [])
                source = self.derive_source(sources, evidence_by_ref)
                if source == "none" and raw.get("evidence"):
                    ev_types = {
                        e.get("source_type")
                        for e in raw["evidence"]
                        if e.get("source_type")
                    }
                    if ev_types == {"pdf", "image"}:
                        source = "both"
                    elif ev_types:
                        source = "".join(sorted(ev_types))

                results.append(
                    {
                        "field_id": fid,
                        "field_name": field_name,
                        "section_name": section_name,
                        "table_id": container_id,
                        "matched": matched,
                        "value": value,
                        "option_id": option_id,
                        "confidence": round(confidence, 3),
                        "reasoning": raw.get("reasoning", ""),
                        "source": source,
                        "mapping_method": raw.get("mapping_method", "unknown"),
                        "source_location": self._source_location(sources),
                    }
                )

                new_field = {k: v for k, v in field.items()}
                if matched:
                    new_field["value"] = value
                    new_field["matched"] = True
                else:
                    new_field["matched"] = False
                new_fields.append(new_field)

            new_container["fields"] = new_fields
            populated_containers.append(new_container)

        if "tables" in form_schema:
            populated["tables"] = populated_containers
        elif "sections" in form_schema:
            populated["sections"] = populated_containers
        else:
            populated["fields"] = populated_containers

        matched_count = sum(1 for r in results if r.get("matched"))
        by_method: Dict[str, int] = {}
        for r in results:
            m = str(r.get("mapping_method") or "unknown")
            by_method[m] = by_method.get(m, 0) + 1
        logger.info(
            "[MAP] build_results complete: containers=%d total=%d matched=%d "
            "unmatched=%d by_method=%s",
            len(containers),
            len(results),
            matched_count,
            len(results) - matched_count,
            by_method,
        )
        return results, populated

    @staticmethod
    def summarize_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate mapping metrics for logs / API response."""
        total = len(results)
        mapped = [r for r in results if r.get("matched")]
        unmatched = [r for r in results if not r.get("matched")]
        by_method: Dict[str, int] = {}
        for r in results:
            m = str(r.get("mapping_method") or "unknown")
            by_method[m] = by_method.get(m, 0) + 1
        conf_bins: Dict[str, int] = {}
        for r in results:
            c = float(r.get("confidence") or 0.0)
            key = f"{min(int(c * 10), 10)}x"
            conf_bins[key] = conf_bins.get(key, 0) + 1
        return {
            "total_fields": total,
            "mapped": len(mapped),
            "unmatched": len(unmatched),
            "unmatched_fields": [r.get("field_name") for r in unmatched[:25]],
            "by_method": by_method,
            "confidence_bins": dict(sorted(conf_bins.items())),
        }

    def collect_containers(self, form_schema: Dict[str, Any]) -> List[Dict]:
        if "tables" in form_schema and isinstance(form_schema["tables"], list):
            return form_schema["tables"]
        if "sections" in form_schema and isinstance(form_schema["sections"], list):
            return form_schema["sections"]
        if "fields" in form_schema and isinstance(form_schema["fields"], list):
            return [{"id": "root", "title": "Root", "fields": form_schema["fields"]}]
        return []

    @staticmethod
    def _source_ref(entry: Any) -> str:
        if isinstance(entry, dict):
            return str(entry.get("ref") or entry.get("source_ref") or "")
        return str(entry or "")

    @classmethod
    def _source_type(cls, entry: Any) -> str:
        if isinstance(entry, dict):
            return str(entry.get("type") or entry.get("source_type") or "")
        return ""

    @classmethod
    def derive_source(cls, sources, evidence_by_ref) -> str:
        if not sources:
            return "none"

        source_types: set = set()
        for entry in sources:
            declared = cls._source_type(entry)
            if declared:
                source_types.add(declared)
                continue
            evt = evidence_by_ref.get(cls._source_ref(entry))
            if evt is not None and evt.source_type:
                source_types.add(evt.source_type)

        if source_types == {"pdf", "image"}:
            return "both"
        return "".join(sorted(source_types)) if source_types else "unknown"

    @classmethod
    def _source_location(cls, sources) -> str:
        """Human-readable ``"; "``-joined list of source refs (shape-tolerant)."""
        if not sources:
            return ""
        refs = [cls._source_ref(entry) for entry in sources]
        return "; ".join(ref for ref in refs if ref)
