from typing import List, Dict

try:
    from sentence_transformers import CrossEncoder
except ImportError:
    CrossEncoder = None


class CrossEncoderReranker:
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-12-v2"):
        if CrossEncoder is None:
            raise RuntimeError("sentence_transformers is not installed")
        self.model = CrossEncoder(model_name)

    def rerank(self, query: str, chunks: List[Dict], top_k: int = 10) -> List[Dict]:
        if not chunks:
            return []

        def chunk_text(c: Dict) -> str:
            if c.get("content"):
                return c["content"]
            meta = c.get("metadata") or {}
            if isinstance(meta, dict) and meta.get("text"):
                return meta["text"]
            parts = [meta.get("field_name", ""), str(meta.get("value", ""))]
            return " ".join(p for p in parts if p)

        pairs = [(query, self._truncate(chunk_text(chunk))) for chunk in chunks]
        scores = self.model.predict(pairs)

        scored = list(zip(chunks, scores))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [chunk for chunk, score in scored[:top_k]]

    @staticmethod
    def _truncate(text: str, limit: int = 400) -> str:
        text = text or ""
        return text if len(text) <= limit else text[:limit]