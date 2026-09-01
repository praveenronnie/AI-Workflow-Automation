"""PDF processing task for Celery.

This is a real Celery task.  It receives a ``job_id`` and a list of local PDF
file entries, runs each file through the appropriate extractor (scanned →
Docling/Modal, handwritten → page‑render + VLM), bulk‑inserts the evidence,
and enqueues the embedding worker before marking the job completed.

Files are passed as paths (not raw bytes) so the payload survives the JSON
broker serializer.  The endpoint persists uploads to disk before enqueuing.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import List

from inspection_ai.celery_app import celery_app
from inspection_ai.core.container import get_universal_services
from inspection_ai.database.base import get_db_session as get_db
from inspection_ai.database.repositories.report_repository import ReportRepository

logger = logging.getLogger(__name__)


async def run_pdf_pipeline(
    job_id: str,
    pdf_entries: List[dict],
    report_id: str,
    user_id: str,
) -> None:
    # Async pipeline shared by the Celery task (and usable for inline fallback).
    async with get_db() as db:
        repo: ReportRepository = ReportRepository(db)  # type: ignore
        try:
            await repo.update_job_status(job_id, "processing")
            logger.info("[PDF] job %s started (%d files)", job_id, len(pdf_entries))

            services = get_universal_services()
            scanned = services.get_extractor("pdf")
            handwritten = services.get_extractor("handwritten")

            # 2️⃣ Create a batch and bulk-insert evidence in one commit
            # Evidence instances from the extractors already have evidence_batch_id set
            # (because we pass batch.id as the batch_id parameter to the extractors)

            batch = await repo.create_batch(report_id)
            all_evidence = []
            for entry in pdf_entries:
                path = entry["path"]
                filename = entry.get("filename", "document.pdf")
                doc_type = entry.get("doc_type", "scanned")

                with open(Path(path), "rb") as fh:
                    pdf_bytes = fh.read()

                if doc_type == "handwritten":
                    # sync extractor -> run off the event loop
                    ev = await asyncio.to_thread(
                        handwritten.extract,
                        None,
                        pdf_bytes,
                        report_id,
                        "",
                        batch.id,  # pass batch_id so Evidence gets evidence_batch_id set
                        filename,
                        user_id,
                        entry.get("document_id"),  # shared knowledge-base doc id
                    )
                else:
                    ev = await scanned.extract(
                        None,
                        pdf_bytes,
                        report_id,
                        "",
                        batch.id,  # pass batch_id so Evidence gets evidence_batch_id set
                        filename,
                        user_id,
                        entry.get("document_id"),  # shared knowledge-base doc id
                    )
                all_evidence.extend(ev or [])
                logger.info(
                    "[PDF] processed %s -> %d evidence", filename, len(ev or [])
                )
                file_id = entry.get("file_id")
                if file_id:
                    await repo.update_file_extraction_state(file_id, "completed")

            evidence_ids = await repo.bulk_insert_evidence(all_evidence)
            logger.info(
                "[PDF] bulk-inserted %d evidence rows", len(evidence_ids)
            )

            if evidence_ids:
                # 3️⃣ Enqueue embedding worker (do NOT await — .delay returns AsyncResult)
                from inspection_ai.tasks.embed_worker import embed_evidence_task

                embed_evidence_task.delay(job_id, evidence_ids)

            # 4️⃣ Complete the batch before marking job done
            await repo.complete_batch(batch.id, len(all_evidence))

            # 5️⃣ Mark job completed
            await repo.update_job_status(job_id, "completed")
            logger.info("[PDF] job %s completed", job_id)
        except Exception as exc:  # noqa: BLE001
            logger.error("[PDF] job %s failed: %s", job_id, exc, exc_info=True)
            for entry in pdf_entries:
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
    name="inspection_ai.tasks.process_pdf",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
)
def process_pdf_task(
    self, job_id: str, pdf_entries: List[dict], report_id: str, user_id: str
) -> None:
    return asyncio.run(run_pdf_pipeline(job_id, pdf_entries, report_id, user_id))
