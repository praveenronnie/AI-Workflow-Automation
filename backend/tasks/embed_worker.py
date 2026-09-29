"""Embedding worker task for Celery.

This task receives a ``job_id`` and a list of evidence ``id``s, fetches the
corresponding evidence records, builds chunk payloads and stores them in the
vector store (Qdrant).  Finally it marks the job as ``completed`` (or
``failed``).

The vector store is optional — when it is unavailable the embeddings are
skipped but the job is still marked completed, so the worker degrades
gracefully instead of poisoning the whole pipeline.
"""

from __future__ import annotations

import asyncio
import logging
from typing import List

from sqlalchemy import select

from backend.celery_app import celery_app
from backend.database.base import get_db_session as get_db
from backend.database.models.evidence import Evidence
from backend.database.repositories.report_repository import ReportRepository

logger = logging.getLogger(__name__)


def evidence_to_chunk(ev: Evidence) -> dict:
    """Build a Qdrant chunk payload from a persisted Evidence row."""
    value = ev.value if isinstance(ev.value, str) else ev.raw_text or ""
    return {
        "id": ev.id,
        "content": f"{ev.field_name or 'evidence'}: {value[:2000]}",
        "metadata": {
            "user_id": ev.user_id,
            "report_id": ev.report_id,
            "file_id": ev.file_id,
            "document_id": ev.document_id,
            "source_type": ev.source_type,
            "source_ref": ev.source_ref,
            "field_name": ev.field_name,
            "value": value,
            "confidence": ev.confidence,
        },
    }


async def store_embeddings(report_id: str, user_id: str, chunks: List[dict]) -> None:
    """Upsert chunks into Qdrant.  Gracefully no‑ops if the store is unavailable."""
    if not chunks:
        return
    try:
        from backend.core.container import get_universal_services

        store = get_universal_services().vector_store
        if store is None:
            logger.warning(
                "[embed] vector store unavailable, skipping (%d chunks)", len(chunks)
            )
            return
        # encode_and_store is async -> await it directly.
        await store.encode_and_store(report_id, user_id, chunks)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[embed] vector store unavailable, skipping embeddings (%d chunks): %s",
            len(chunks),
            exc,
        )


async def run_embed_pipeline(job_id: str, evidence_ids: List[str]) -> None:
    async with get_db() as db:
        repo: ReportRepository = ReportRepository(db)  # type: ignore
        try:
            if not evidence_ids:
                await repo.update_job_status(job_id, "completed")
                return

            evidence_rows = (
                (
                    await repo.session.execute(
                        select(Evidence).where(Evidence.id.in_(evidence_ids))
                    )
                )
                .scalars()
                .all()
            )
            logger.info("[embed] fetched %d evidence rows", len(evidence_rows))
            if not evidence_rows:
                await repo.update_job_status(job_id, "completed")
                return

            chunks = [evidence_to_chunk(ev) for ev in evidence_rows]

            # Pull scope metadata from the first row (they share report/user).
            first = evidence_rows[0]
            await store_embeddings(first.report_id, first.user_id, chunks)

            logger.info("[embed] embedded %d items (job %s)", len(chunks), job_id)
            await repo.update_job_status(job_id, "completed")
        except Exception as exc:  # noqa: BLE001
            logger.error("[embed] job %s failed: %s", job_id, exc, exc_info=True)
            try:
                await repo.update_job_status(job_id, "failed", str(exc))
            finally:
                raise


@celery_app.task(
        name="backend.tasks.embed_evidence",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def embed_evidence_task(self, job_id: str, evidence_ids: List[str]) -> None:
    # Celery entry point.  Delegates to the async pipeline via ``asyncio.run``.
    logger.info("Entered Celery worker for embedding")
    return asyncio.run(run_embed_pipeline(job_id, evidence_ids))
