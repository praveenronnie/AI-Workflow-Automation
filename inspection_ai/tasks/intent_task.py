"""Intent pre-pass task for Celery.

Normalizes the stored form schema and computes the section intent for *every*
section in parallel, persisting each section (report_intents table) plus the
Redis fast cache.  Also exposes ``ensure_report_intents`` used as a fallback by
the map pipeline when the pre-pass did not run (e.g. non-OpenQuire URL).
"""

from __future__ import annotations

import asyncio
import logging


from inspection_ai.celery_app import celery_app
from inspection_ai.config import get_settings
from inspection_ai.database.base import get_db_session as get_db
from inspection_ai.database.repositories.report_repository import ReportRepository
from inspection_ai.universal_service.mapper.form_schema_adapter import (
    normalize_form_schema,
)
from inspection_ai.universal_service.mapper.universal_mapper import UniversalMapper

logger = logging.getLogger(__name__)


async def ensure_report_intents(report_id: str, repo: ReportRepository) -> int:
    """Compute and persist intents for every section (idempotent).

    Returns the number of sections processed.
    """
    fs = await repo.get_form_schema_for_report(report_id)
    if fs is None or not fs.schema_json:
        return 0
    schema, _field_meta = normalize_form_schema(fs.schema_json)
    sections = getattr(schema, "sections", [])
    if not sections:
        return 0
    if await repo.are_intents_ready(report_id, len(sections)):
        logger.info("[Intent] already ready: report_id=%s sections=%d", report_id, len(sections))
        return len(sections)

    from inspection_ai.universal_service.api.dependencies import get_universal_services

    services = get_universal_services()

    # Resolve the domain dynamically from the database (first active domain)
    # instead of hardcoding a slug — keeps the task domain-agnostic.
    domain_name = None
    try:
        default_domain = await repo.get_default_domain()
        if default_domain is not None:
            domain_name = default_domain.name
    except Exception as exc:  # noqa: BLE001
        logger.warning("[Intent] default domain lookup failed: %s", exc)
    if not domain_name:
        domain_name = "pca_site_assessment"  # last-resort fallback

    mapper = UniversalMapper(
        llm_client=services.llm,
        vector_store=None,
        reranker=None,
        redis_client=services.redis_cache,
        domain=domain_name,
        min_confidence=0.6,
    )
    settings = get_settings()
    semaphore = asyncio.Semaphore(getattr(settings, "max_concurrent_llm_calls", 3))

    async def detect(section):
        async with semaphore:
            intent = {}
            try:
                intent = await mapper.get_section_intent(
                    section.id, section.title, section.fields, report_id=report_id
                )
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "[Intent] section intent failed section=%s report=%s error=%s",
                    section.id,
                    report_id,
                    exc,
                )
            try:
                await repo.save_section_intent(
                    report_id, section.id, section.title, len(section.fields), intent or {}
                )
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "[Intent] persist failed section=%s report=%s error=%s",
                    section.id,
                    report_id,
                    exc,
                )

    await asyncio.gather(*[detect(s) for s in sections])
    logger.info("[Intent] pre-pass complete report=%s sections=%d", report_id, len(sections))
    return len(sections)


async def run_intent_prepass(job_id: str, report_id: str, user_id: str) -> None:
    async with get_db() as db:
        repo = ReportRepository(db)
        try:
            await repo.update_job_status(job_id, "processing")
            count = await ensure_report_intents(report_id, repo)
            await repo.update_job_status(job_id, "completed")
            logger.info("[Intent] job %s completed: report_id=%s sections=%d", job_id, report_id, count)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "[Intent] job %s failed: report_id=%s error=%s",
                job_id,
                report_id,
                exc,
                exc_info=True,
            )
            await repo.update_job_status(job_id, "failed", str(exc))


@celery_app.task(
    name="inspection_ai.tasks.intents",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
)
def trigger_intent_task(self, job_id: str, report_id: str, user_id: str) -> None:
    logger.info("Entered intent pre-pass worker: report=%s", report_id)
    return asyncio.run(run_intent_prepass(job_id, report_id, user_id))