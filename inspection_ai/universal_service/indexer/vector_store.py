import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from inspection_ai.config import get_settings
from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    PointStruct,
    VectorParams,
    Distance,
    Filter,
    FieldCondition,
    MatchText,
    MatchValue,
    MatchAny,
    QueryRequest,
    SparseVectorParams,
    SparseVector,
    SparseIndexParams,
    ScalarQuantization,
    ScalarQuantizationConfig,
    ScalarType,
    PayloadSchemaType,
    WriteOrdering,
    Prefetch,
    Fusion,
    FusionQuery,
)

try:
    import modal
except ImportError:
    modal = None

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None

try:
    from sklearn.feature_extraction.text import HashingVectorizer
except ImportError:
    HashingVectorizer = None

# NOTE: ``get_modal_executor`` is imported lazily inside the embedding call
# below. Importing it at module level creates a circular import
# (vector_store → api.dependencies → mapper.universal_mapper → alias_resolver
# → vector_store) that breaks any fresh import of the mapper package.

logger = logging.getLogger(__name__)

SPARSE_DIM = 20000
SCORE_THRESHOLD = 0.3


@dataclass
class SearchQuery:
    canonical_name: str
    definition_id: str
    section_id: str
    top_k: int = 5
    source_type: Optional[str] = None
    extra_filter: Optional[Dict[str, Any]] = None
    # Shared knowledge base: scope retrieval to the report's linked documents.
    # When set, this replaces the report_id payload filter (evidence belongs to
    # documents, which may be linked to many reports).
    document_ids: Optional[List[str]] = None


@dataclass
class GroupedMatch:
    by_field: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    by_section: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    latency_ms: float = 0.0


class SparseTokenizer:
    def __init__(self, n_features=SPARSE_DIM):
        self.n_features = n_features
        self.vectorizer = HashingVectorizer(
            n_features=n_features,
            alternate_sign=False,
            norm="l2",
        )

    def encode(self, texts):
        mat = self.vectorizer.transform(texts)
        result = []
        for i in range(mat.shape[0]):
            s = mat.indptr[i]
            e = mat.indptr[i + 1]
            result.append(
                SparseVector(
                    indices=mat.indices[s:e].tolist(),
                    values=mat.data[s:e].tolist(),
                )
            )
        return result


class UniversalVectorStore:
    def __init__(
        self,
        collection_name: str = "universal_evidence",
        host: str = None,
        port: int = None,
    ):
        # Qdrant is reachable at different hosts depending on where this runs:
        # on the host machines it is localhost, inside the Docker containers it is
        # the service name (VECTOR_DB_URL env, set in docker-compose).  Defaults
        # fall back to localhost for local development.
        settings = get_settings()
        url = (
            getattr(settings, "vector_db_url", "http://localhost:6333")
            or "http://localhost:6333"
        )
        api_key = getattr(settings, "vector_db_api_key", "") or None
        self.collection_name = (
            collection_name
            if collection_name != "universal_evidence"
            else getattr(settings, "vector_db_index_name", "universal_evidence")
        )
        self.embedding_model = getattr(
            settings, "embedding_model", "BAAI/bge-large-en-v1.5"
        )
        self.dimension = int(getattr(settings, "vector_db_dimension", 1024))
        self.client = QdrantClient(url=url, api_key=api_key)
        self.sparse_tokenizer = SparseTokenizer() if HashingVectorizer else None
        self.indexed_fields = [
            "report_id",
            "document_id",
            "user_id",
            "source_type",
            "section_id",
            "definition_id",
            "canonical_name",
            "chunk_kind",
        ]
        self.ensure_collection()

    def ensure_collection(self):
        # Create the Qdrant collection if it does not already exist.
        try:
            if self.client.collection_exists(self.collection_name):
                logger.info(
                    "Collection %s already exists",
                    self.collection_name,
                )
                return
            logger.info(
                "Collection %s does not exist. Creating...",
                self.collection_name,
            )
            self._create_collection()

        except Exception:
            logger.exception(
                "Failed to ensure collection %s",
                self.collection_name,
            )
            raise

    def _create_collection(self):
        # Create the Qdrant collection with dense and optional sparse vectors.
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config={
                "dense": self._dense_vector_config(),
            },
            sparse_vectors_config={
                "sparse": self._sparse_vector_config(),
            },
            quantization_config=ScalarQuantization(
                scalar=ScalarQuantizationConfig(
                    type=ScalarType.INT8,
                    quantile=0.99,
                    always_ram=True,
                )
            ),
        )
        vector_types = ["dense", "sparse"] if self.sparse_tokenizer else ["dense"]
        logger.info(
            "Created collection %s with %s vectors",
            self.collection_name,
            vector_types,
        )

    def _dense_vector_config(self):
        # Return the dense vector configuration.
        return VectorParams(
            size=self.dimension,
            distance=Distance.COSINE,
        )

    def _sparse_vector_config(self):
        # Return the sparse vector configuration.
        return SparseVectorParams(
            index=SparseIndexParams(
                on_disk=False,
            )
        )

    def ensure_payload_indexes(self):
        # KEYWORD (filterable) vs TEXT (full-text search) — pick per field.
        keyword_fields = {
            "report_id",
            "user_id",
            "source_type",
            "section_id",
            "definition_id",
            "chunk_kind",
        }
        for field_name in self.indexed_fields:
            try:
                schema = (
                    PayloadSchemaType.KEYWORD
                    if field_name in keyword_fields
                    else PayloadSchemaType.TEXT
                )
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field_name,
                    field_schema=schema,
                )
            except Exception:
                pass

    async def encode_batch(self, texts: List[str]) -> List[List[float]]:
        try:
            # Lazy import to avoid the circular dependency described above.
            from inspection_ai.universal_service.api.dependencies import (
                get_modal_executor,
            )

            if get_modal_executor() is not None:
                embeddings = await get_modal_executor().execute_modal_embedding(texts)
                return embeddings
            return self.encode_cpu(texts)
        except Exception as e:
            logger.info("Embedding Failed...", e)
            return []

    def encode_cpu(self, texts: List[str]) -> List[List[float]]:
        if SentenceTransformer is None:
            raise RuntimeError("sentence_transformers is not installed")
        model = SentenceTransformer(self.embedding_model, device="cpu")
        embeddings = model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            batch_size=32,
        ).astype("float32")
        return embeddings.tolist()

    def upsert(self, chunks, embeddings, sparse_vectors=None):
        if sparse_vectors is None and self.sparse_tokenizer:
            contents = [c.get("content") or c.get("text") or "" for c in chunks]
            sparse_vectors = self.sparse_tokenizer.encode(contents)
        points = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            vector = {"dense": embedding}
            if sparse_vectors and i < len(sparse_vectors):
                vector["sparse"] = sparse_vectors[i]
            # Merge chunk metadata with section/correlation context so the
            # retriever can filter & group without an extra round-trip.
            meta = chunk.get("metadata") or {}
            payload = {
                **meta,
                "id": chunk["id"],
                "text": chunk.get("content") or chunk.get("text", ""),
                "section_id": chunk.get("section_id") or meta.get("section_id"),
                "definition_id": chunk.get("definition_id")
                or meta.get("definition_id"),
                "canonical_name": chunk.get("canonical_name")
                or meta.get("canonical_name"),
                "chunk_kind": chunk.get("chunk_kind", meta.get("chunk_kind", "prose")),
                "doc_id": chunk.get("doc_id") or meta.get("doc_id"),
                "source_type": chunk.get("source_type") or meta.get("source_type"),
            }
            # Drop None values so the payload stays compact and payload-indexable.
            payload = {k: v for k, v in payload.items() if v is not None}
            points.append(
                PointStruct(
                    id=self.generate_point_id(chunk["id"]),
                    vector=vector,
                    payload=payload,
                )
            )
        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
            ordering=WriteOrdering.STRONG,
        )

    async def search(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict] = None,
        user_id: Optional[str] = None,
        report_id: Optional[str] = None,
        score_threshold: Optional[float] = None,
    ) -> List[Dict]:
        query_embedding = (await self.encode_batch([query]))[0]
        qdrant_filter = self.build_filter(filters, user_id=user_id, report_id=report_id)
        if query_embedding is None:
            return []
        prefetch = [
            Prefetch(
                query=query_embedding,
                using="dense",
                filter=qdrant_filter,
                limit=top_k * 3,
            ),
        ]
        if self.sparse_tokenizer:
            sparse_vec = self.sparse_tokenizer.encode([query])[0]
            prefetch.append(
                Prefetch(
                    query=sparse_vec,
                    using="sparse",
                    filter=qdrant_filter,
                    limit=top_k * 3,
                ),
            )
        results = self.client.query_points(
            collection_name=self.collection_name,
            prefetch=prefetch,
            query=FusionQuery(fusion=Fusion.RRF),
            filter=qdrant_filter,
            score_threshold=score_threshold or SCORE_THRESHOLD,
            limit=top_k,
            with_payload=True,
            with_vectors=False,
        )
        normalized = []
        for r in results.points:
            if not r.payload:
                continue
            cid = r.payload.get("id")
            metadata = {k: v for k, v in r.payload.items() if k != "id"}
            normalized.append({"id": cid or "", "metadata": metadata})
        return normalized

    async def search_batch(
        self,
        queries: List[Any],
        top_k: int = 10,
        filters: Optional[Dict] = None,
        user_id: Optional[str] = None,
        report_id: Optional[str] = None,
        document_ids: Optional[List[str]] = None,
        score_threshold: Optional[float] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Batch vector search across a list of queries.

        ``queries`` may be either a list of plain strings (backward-compatible
        behaviour) or a list of :class:`SearchQuery` objects.  When
        ``SearchQuery`` objects are supplied the returned structure is keyed by
        ``definition_id`` (under ``by_field``) and by section id (under
        ``by_section``), which is exactly what the
        :class:`~inspection_ai.universal_service.mapper.universal_mapper.UniversalMapper`
        consumes for section-grouped retrieval.
        """
        if not queries:
            return {"by_field": {}, "by_section": {}, "latency_ms": 0.0}

        start = time.perf_counter()

        # Normalise the query list: accept both strings and SearchQuery objects.
        normalized_queries: List[SearchQuery] = []
        query_texts: List[str] = []
        for q in queries:
            if isinstance(q, SearchQuery):
                normalized_queries.append(q)
                query_texts.append(q.canonical_name or q.definition_id or "")
            elif isinstance(q, str):
                normalized_queries.append(
                    SearchQuery(
                        canonical_name=q,
                        definition_id=q,
                        section_id="",
                    )
                )
                query_texts.append(q)
            else:
                logger.warning(
                    "Ignoring unsupported query type in search_batch: %r", type(q)
                )
        if not query_texts:
            return {"by_field": {}, "by_section": {}, "latency_ms": 0.0}

        query_embeddings = await self.encode_batch(query_texts)
        qdrant_filter = self.build_filter(
            filters,
            user_id=user_id,
            report_id=report_id,
            document_ids=document_ids,
        )
        sparse_vectors = None
        if self.sparse_tokenizer:
            sparse_vectors = self.sparse_tokenizer.encode(query_texts)
        requests = []
        for i, dense in enumerate(query_embeddings):
            qobj = normalized_queries[i]
            # Allow per-query filters (e.g. section scoping) to narrow results.
            per_query_filter = qdrant_filter
            if qobj.extra_filter:
                per_query_filter = self.merge_filters(qdrant_filter, qobj.extra_filter)
            if dense is None:
                requests.append(QueryRequest(limit=top_k))
                continue
            prefetch = [
                Prefetch(
                    query=dense, using="dense", filter=per_query_filter, limit=top_k * 3
                ),
            ]
            if sparse_vectors and i < len(sparse_vectors):
                prefetch.append(
                    Prefetch(
                        query=sparse_vectors[i],
                        using="sparse",
                        filter=per_query_filter,
                        limit=top_k * 3,
                    ),
                )
            requests.append(
                QueryRequest(
                    prefetch=prefetch,
                    query=FusionQuery(fusion=Fusion.RRF),
                    filter=per_query_filter,
                    score_threshold=score_threshold or SCORE_THRESHOLD,
                    limit=top_k,
                    with_payload=True,
                )
            )
        batch_response = self.client.query_batch_points(
            collection_name=self.collection_name,
            requests=requests,
        )

        # Group results by field definition id and section id for the mapper's
        # section-grouped retrieval path.
        by_field: Dict[str, Dict[str, Any]] = {}
        by_section: Dict[str, Dict[str, Any]] = {}
        for qobj, result_group in zip(normalized_queries, batch_response):
            normalized_local: List[Dict[str, Any]] = []
            for r in result_group.points:
                if not r.payload:
                    continue
                cid = r.payload.get("id")
                metadata = {k: v for k, v in r.payload.items() if k != "id"}
                normalized_local.append({"id": cid or "", "metadata": metadata})
            key = qobj.definition_id or qobj.canonical_name or ""
            if key:
                existing = by_field.setdefault(key, {"matches": []})
                existing["matches"].extend(normalized_local)
                existing.setdefault("canonical_name", qobj.canonical_name)
                existing.setdefault("definition_id", qobj.definition_id)
                existing.setdefault("section_id", qobj.section_id)
            sec_key = qobj.section_id
            if sec_key:
                sec_bucket = by_section.setdefault(
                    sec_key, {"matches": [], "queries": []}
                )
                sec_bucket["matches"].extend(normalized_local)
                sec_bucket["queries"].append(qobj.canonical_name or qobj.definition_id)

        latency_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "Batch search %d queries top_k=%d report=%s latency_ms=%.1f",
            len(query_texts),
            top_k,
            report_id,
            latency_ms,
        )
        return {
            "by_field": by_field,
            "by_section": by_section,
            "latency_ms": latency_ms,
        }

    @staticmethod
    def build_filter(
        filters: Optional[Dict],
        user_id: Optional[str] = None,
        report_id: Optional[str] = None,
        document_ids: Optional[List[str]] = None,
    ):
        conditions = []
        if filters:
            for field, value in filters.items():
                conditions.append(
                    FieldCondition(key=field, match=MatchText(text=str(value)))
                )
        # Shared knowledge base: when scoping by the report's linked documents,
        # the uploader's ``user_id`` must NOT filter the results. Documents are
        # globally deduplicated and linked to many reports, and each report may
        # be worked on by several users (report_users). A filter of
        # ``user_id == caller AND document_id IN (shared docs)`` returns nothing
        # whenever a report's documents were uploaded by another user.
        if user_id and not document_ids:
            conditions.append(
                FieldCondition(key="user_id", match=MatchValue(value=user_id))
            )
        if document_ids:
            # Shared knowledge base: match ANY of the report's linked documents
            conditions.append(
                FieldCondition(key="document_id", match=MatchAny(any=document_ids))
            )
        elif report_id:
            conditions.append(
                FieldCondition(key="report_id", match=MatchValue(value=report_id))
            )
        return Filter(must=conditions) if conditions else None

    def merge_filters(
        self, base: Optional[Filter], extra: Optional[Dict[str, Any]]
    ) -> Optional[Filter]:
        if not extra:
            return base
        conditions = list(base.must) if base and base.must else []
        for field, value in extra.items():
            if value is None:
                continue
            conditions.append(
                FieldCondition(
                    key=field,
                    match=(
                        MatchText(text=str(value))
                        if isinstance(value, str)
                        else MatchValue(value=value)
                    ),
                )
            )
        return Filter(must=conditions) if conditions else None

    def delete_by_scope(self, user_id: Optional[str], report_id: Optional[str]):
        if not user_id and not report_id:
            return
        qdrant_filter = self.build_filter(None, user_id=user_id, report_id=report_id)
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=qdrant_filter,
        )

    def existing_point_ids(self, report_id, user_id) -> set:
        """Return the set of already-indexed point ids for a report/user (for delta upserts)."""
        ids = set()
        qdrant_filter = self.build_filter(None, user_id=user_id, report_id=report_id)
        try:
            offset = None
            while True:
                points, next_offset = self.client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=qdrant_filter,
                    with_payload=False,
                    limit=1000,
                    offset=offset,
                )
                for p in points:
                    ids.add(p.id)
                if next_offset is None or getattr(next_offset, "offset", None) is None:
                    break
                offset = next_offset.offset
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[embed] scroll existing failed (will re-index): report=%s err=%s",
                report_id,
                exc,
            )
        return ids

    async def encode_and_store(
        self,
        report_id: Optional[str],
        user_id: Optional[str],
        chunks: List[Dict],
    ):
        if not chunks:
            return

        try:
            # Delta embeddings: skip chunks already upserted for this report/user.
            existing = self.existing_point_ids(report_id, user_id)
            fresh = []
            for chunk in chunks:
                point_id = self.generate_point_id(chunk.get("id"))
                if point_id not in existing:
                    fresh.append(chunk)
            if not fresh:
                logger.info(
                    "[embed] all %d chunks already indexed: report=%s user=%s",
                    len(chunks),
                    report_id,
                    user_id,
                )
                return

            texts = [chunk["content"] for chunk in fresh]
            logger.info(
                "[embed] embedding %d new chunks (skipped %d): report=%s user=%s",
                len(texts),
                len(chunks) - len(fresh),
                report_id,
                user_id,
            )
            embeddings = await self.encode_batch(texts)
            self.upsert(fresh, embeddings)
            logger.info(
                "Stored %d new vectors in %s (report=%s)",
                len(fresh),
                self.collection_name,
                report_id,
            )
        except Exception as e:
            logger.error("encode_and_store failed: %s", e)

    @staticmethod
    def generate_point_id(chunk_id) -> int:
        if isinstance(chunk_id, int):
            return chunk_id
        return int(hashlib.md5(str(chunk_id).encode()).hexdigest()[:16], 16)
