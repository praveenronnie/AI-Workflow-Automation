from ..models.evidence import Evidence


class EvidenceIndexer:
    def __init__(self, vector_store, bm25_index=None):
        self.vector_store = vector_store
        self.bm25_index = bm25_index

    def chunk_to_evidence(self, chunk: dict) -> Evidence:
        if isinstance(chunk, Evidence):
            return chunk
        if not isinstance(chunk, dict):
            return chunk
        if "metadata" not in chunk:
            meta = {k: v for k, v in chunk.items() if k != "id"}
            cid = chunk.get("id", "")
        else:
            meta = chunk.get("metadata", {})
            if not isinstance(meta, dict):
                meta = {}
            cid = chunk.get("id", "")
        if isinstance(meta.get("evidence"), Evidence):
            return meta["evidence"]
        value = meta.get("value", "")
        return Evidence(
            id=cid,
            evidence_batch_id=meta.get("evidence_batch_id", ""),
            session_id=meta.get("session_id", ""),
            report_id=meta.get("report_id", ""),
            user_id=meta.get("user_id"),
            file_id=meta.get("file_id"),
            source_type=meta.get("source_type", ""),
            source_ref=meta.get("source_ref", ""),
            document_hash=meta.get("document_hash"),
            content_hash=meta.get("content_hash"),
            field_name=meta.get("field_name", ""),
            value=value,
            data_type=meta.get("data_type", "string"),
            confidence=meta.get("confidence", 0.0),
            category=meta.get("category"),
            subcategory=meta.get("subcategory"),
            tags=meta.get("tags", []),
            extraction_model="indexed",
            timestamp=meta.get("timestamp", ""),
        )