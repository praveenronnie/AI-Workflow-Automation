"""Image processing task for Celery.

This is a real Celery task.  It receives a ``job_id`` and a list of local image
file paths, runs the VLM extractor over the images (batching + parallel batch
dispatch), bulk-inserts the evidence, and enqueues the embedding worker before
marking the job completed.

Files are passed as paths (not raw bytes) so the payload survives the JSON
broker serializer.
"""

from __future__ import annotations

import asyncio
import logging
from typing import List
from pathlib import Path

from inspection_ai.celery_app import celery_app
from inspection_ai.core.config import get_settings
from inspection_ai.ai.config import get_rag_config
from inspection_ai.database.base import get_db_session as get_db
from inspection_ai.database.repositories.report_repository import ReportRepository
from inspection_ai.ai.extraction.image_extractor import ImageExtractor
from inspection_ai.tasks.embed_worker import run_embed_pipeline

logger = logging.getLogger(__name__)


async def run_image_pipeline(
    job_id: str,
    image_entries: List[dict],
    report_id: str,
    user_id: str,
) -> None:
    # Async pipeline shared by the Celery task (usable for inline fallback).
    settings = get_settings()
    rag = get_rag_config()
    async with get_db() as db:
        repo: ReportRepository = ReportRepository(db)  # type: ignore
        try:
            await repo.update_job_status(job_id, "processing")
            logger.info("[IMAGE] job %s started (%d files)", job_id, len(image_entries))

            extractor = ImageExtractor()  # vector_store=None -> embeds via embed worker
            batch_size = rag.llm_image_batch_size or 10
            semaphore = asyncio.Semaphore(settings.max_concurrent_llm_calls)

            batches: List[List[tuple]] = []
            for i in range(0, len(image_entries), batch_size):
                batch = []
                for entry in image_entries[i : i + batch_size]:
                    with open(Path(entry["path"]), "rb") as fh:
                        batch.append((entry.get("filename", "image.jpg"), fh.read()))
                batches.append(batch)

            loop = asyncio.get_running_loop()

            async def run_batch(batch: List[tuple]) -> list:
                async with semaphore:
                    # process_batch is synchronous/blocking (sync LLM call)
                    return await loop.run_in_executor(
                        None, extractor.process_batch, batch
                    )

            # 2) Parallel batch dispatch, bounded by max_concurrent_llm_calls
            results_batches = await asyncio.gather(*[run_batch(b) for b in batches])

            all_results: list = []
            for res in results_batches:
                all_results.extend(res or [])

            # 3) Create Batch
            batch = await repo.create_batch(report_id)
            # filename -> knowledge-base document id (see upload endpoint)
            document_ids = {
                e.get("filename"): e.get("document_id")
                for e in image_entries
                if e.get("document_id")
            }
            all_evidence = extractor.to_evidence(
                all_results,
                None,
                report_id,
                "",
                batch.id,
                user_id,
                document_ids,
            )

            evidence_ids = await repo.bulk_insert_evidence(all_evidence)
            logger.info("[IMAGE] bulk-inserted %d evidence rows", len(evidence_ids))

            if evidence_ids:
                # 4) Enqueue embedding worker (do NOT await -- .delay returns AsyncResult)
                """from inspection_ai.tasks.embed_worker import embed_evidence_task
                embed_evidence_task.delay(job_id, evidence_ids)"""

                try:
                    await run_embed_pipeline(job_id, evidence_ids)
                except Exception as e:
                    logger.info(f"Embedding failed for Job-id: {job_id}", e)

            # 5) Complete the batch before marking job done
            await repo.complete_batch(
                batch.id, len(all_evidence) if all_evidence else 0
            )

            # 6) Mark job completed
            await repo.update_job_status(job_id, "completed")
            logger.info("[IMAGE] job %s completed", job_id)

            for entry in image_entries:
                file_id = entry.get("file_id")
                if file_id:
                    await repo.update_file_extraction_state(file_id, "completed")
        except Exception as exc:  # noqa: BLE001
            logger.error("[IMAGE] job %s failed: %s", job_id, exc, exc_info=True)
            for entry in image_entries:
                file_id = entry.get("file_id")
                if file_id:
                    try:
                        await repo.update_file_extraction_state(
                            file_id, "failed", str(exc)
                        )
                    except Exception:  # noqa: BLE001
                        pass
            await repo.update_job_status(job_id, "failed", str(exc))
            raise


@celery_app.task(
    name="inspection_ai.tasks.process_image",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
)
def process_image_task(
    self, job_id: str, image_entries: List[dict], report_id: str, user_id: str
) -> None:
    return asyncio.run(run_image_pipeline(job_id, image_entries, report_id, user_id))
