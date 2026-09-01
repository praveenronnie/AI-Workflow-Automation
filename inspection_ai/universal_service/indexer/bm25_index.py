import math
from typing import List, Dict


class BM25Index:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.documents: List[str] = []
        self.doc_chunks: List[Dict] = []
        self.doc_lengths: List[int] = []
        self.doc_freq: Dict[str, int] = {}
        self.avg_dl: float = 0.0

    def add_documents(self, documents: List[str], chunks: List[Dict] = None):
        for doc in documents:
            self.documents.append(doc)
            self.doc_chunks.append(chunks[len(self.doc_chunks)] if chunks else {})
            tokens = self.tokenize(doc)
            self.doc_lengths.append(len(tokens))
            for token in set(tokens):
                self.doc_freq[token] = self.doc_freq.get(token, 0) + 1
        self.avg_dl = (
            sum(self.doc_lengths) / len(self.doc_lengths) if self.doc_lengths else 0.0
        )

    def search(self, query: str, top_k: int = 50) -> List[Dict]:
        if not self.documents:
            return []

        query_tokens = self.tokenize(query)
        scores = []
        N = len(self.documents)
        for idx, doc in enumerate(self.documents):
            doc_tokens = self.tokenize(doc)
            score = 0.0
            tf = {}
            for t in doc_tokens:
                tf[t] = tf.get(t, 0) + 1
            dl = self.doc_lengths[idx]
            for q in query_tokens:
                if q not in tf:
                    continue
                idf = math.log(1 + (N - self.doc_freq.get(q, 0) + 0.5) / (self.doc_freq.get(q, 0) + 0.5))
                tf_q = tf[q]
                score += idf * (tf_q * (self.k1 + 1)) / (tf_q + self.k1 * (1 - self.b + self.b * dl / self.avg_dl))
            scores.append((idx, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        results = []
        for idx, score in scores[:top_k]:
            chunk = self.doc_chunks[idx] if idx < len(self.doc_chunks) else {}
            chunk = dict(chunk)
            chunk["content"] = self.documents[idx]
            chunk.setdefault("metadata", {})
            chunk["metadata"]["bm25_score"] = score
            results.append(chunk)
        return results

    @staticmethod
    def tokenize(text: str) -> List[str]:
        return [t for t in text.lower().split() if t]