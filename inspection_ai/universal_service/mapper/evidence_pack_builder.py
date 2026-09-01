from typing import List, Dict

from ..models.evidence import Evidence
from ..models.form_schema import FormField


class EvidencePackBuilder:
    MAX_EVIDENCE = 6
    MIN_CONFIDENCE = 0.6
    MAX_RAW_LEN = 200
    MAX_VALUE_LEN = 150
    MAX_SUMMARY_LEN = 1500

    def build(self, field: FormField, evidence: List[Evidence]) -> Dict:
        """Build an LLM-friendly pack.

        Includes **all** evidence (low-confidence tagged) so the LLM is never
        starved of context, and exposes a compact ``summary``/``content`` key
        that the batch prompt reads directly (instead of a truncated repr).
        """
        ordered = sorted(evidence, key=lambda e: e.confidence, reverse=True)
        relevant = ordered[: self.MAX_EVIDENCE]

        pack = {
            "field": {
                "id": field.id,
                "label": field.label,
                "type": field.type,
                "options": field.options,
            },
            "evidence": [],
            "summary": "",
            "content": "",
        }

        for evt in relevant:
            value_str = str(evt.value) if evt.value is not None else "null"
            low_conf = evt.confidence < self.MIN_CONFIDENCE
            pack["evidence"].append(
                {
                    "source": evt.source_type,
                    "value": value_str[: self.MAX_VALUE_LEN],
                    "confidence": evt.confidence,
                    "ref": evt.source_ref,
                    "field_name": evt.field_name,
                    "raw": (evt.raw_text or "")[: self.MAX_RAW_LEN] if evt.raw_text else None,
                    "low_conf": low_conf,
                }
            )

        summary = self._summarize(field, relevant, total=len(ordered))
        pack["summary"] = summary
        pack["content"] = summary
        return pack

    def _summarize(
        self, field: FormField, evidence: List[Evidence], total: int
    ) -> str:
        lines = [f"Field: {field.label} (type: {field.type})"]
        if field.options:
            lines.append("Options: " + ", ".join(str(o) for o in field.options))
        if not evidence:
            lines.append("No supporting evidence retrieved for this field.")
        for evt in evidence:
            tag = "" if evt.confidence >= self.MIN_CONFIDENCE else " [LOW-CONF]"
            lines.append(
                f"- {evt.source_type or 'unknown'}:{evt.field_name} = "
                f"{evt.value} (conf {evt.confidence:.2f}{tag})"
            )
            if evt.raw_text:
                lines.append(f"    raw: {evt.raw_text[:120]}")
        if total > len(evidence):
            lines.append(f"({total - len(evidence)} more candidates omitted)")
        return "\n".join(lines)[: self.MAX_SUMMARY_LEN]