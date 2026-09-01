"""Business logic for the reports feature: mapping, locking, pipelines."""

import asyncio
import hashlib
import inspect
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from functools import partial

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from inspection_ai.ai.mapping.alias_resolver import AliasResolver, load_alias_resolver
from inspection_ai.ai.mapping.form_schema_adapter import normalize_form_schema
from inspection_ai.ai.mapping.universal_mapper import UniversalMapper
from inspection_ai.ai.models.evidence import Evidence as UniversalEvidence
from inspection_ai.core.paths import UPLOAD_DIR
from inspection_ai.database.models.user import OrganizationMember, User, UserRole
from inspection_ai.database.repositories.document_repository import DocumentRepository
from inspection_ai.database.repositories.report_repository import ReportRepository
from inspection_ai.database.repositories.user_repository import UserRepository
from inspection_ai.features.mapping.service import MappingHandler
from inspection_ai.features.mapping.upload_handler import UploadedFile

logger = logging.getLogger(__name__)


async def resolve_organization(db: AsyncSession, user: User) -> str:
    result = await db.execute(
        select(OrganizationMember)
        .where(
            OrganizationMember.user_id == user.id,
            OrganizationMember.role == UserRole.owner,
        )
        .limit(1)
    )
    member = result.scalar_one_or_none()
    if member is None:
        org = await UserRepository(db).create_organization(
            name=user.email.split("@")[0],
            slug=user.email.split("@")[0],
            owner_id=user.id,
        )
        return org.id
    return member.organization_id
def get_services():
    """Return the started universal services singleton (deferred import)."""
    from inspection_ai.core.container import (
        get_universal_services,
    )

    return get_universal_services()
DEFAULT_DOMAIN_SLUG = "pca_site_assessment"
DEFAULT_DOMAIN_ID = 1
async def run_mapping(
    report_id: str, user_id: str, db: AsyncSession, domain_id: int = DEFAULT_DOMAIN_ID
) -> dict:
    repo = ReportRepository(db)
    report = await repo.get_report(report_id)
    if report is None:
        raise ValueError("Report not found")
    fs = await repo.get_form_schema_for_report(report_id)
    if fs is None or not fs.schema_json:
        raise ValueError("No form schema found for report")
    form_schema = fs.schema_json

    db_evidence = await repo.get_evidence(report_id)
    if not db_evidence:
        raise ValueError("No evidence found for report")

    session_id = report.session_id or ""
    universal_evidence = [
        UniversalEvidence(
            id=e.id,
            evidence_batch_id=e.batch_id or "",
            session_id=session_id,
            report_id=report_id,
            user_id=e.user_id or user_id,
            source_type=e.source_type or "unknown",
            source_ref=e.source_ref or "",
            document_hash=None,
            content_hash=None,
            field_name=e.field_name or "",
            value=e.value,
            data_type=e.data_type or "string",
            confidence=e.confidence if e.confidence is not None else 0.0,
            raw_text=e.raw_text,
            category=e.category,
            subcategory=e.subcategory,
            tags=e.tags or [],
            extraction_model=e.extraction_model or "unknown",
            timestamp="",
        )
        for e in db_evidence
    ]

    # --- Resolve domain (from front‑end provided domain_id) --------------------
    domain = await repo.get_domain_by_id(domain_id)
    if domain is None:
        logger.warning(
            "[MAP] domain_id=%s not found, falling back to default id=%s",
            domain_id,
            DEFAULT_DOMAIN_ID,
        )
        domain = await repo.get_domain_by_id(DEFAULT_DOMAIN_ID)
    report_domain = domain.name if domain else DEFAULT_DOMAIN_SLUG
    logger.info(
        "[MAP] domain resolved: domain_id=%s domain_name=%s report_id=%s",
        domain_id,
        report_domain,
        report_id,
    )

    schema, field_meta = normalize_form_schema(form_schema, domain=report_domain)

    services = get_services()
    mapper = UniversalMapper(
        llm_client=services.llm,
        vector_store=services.vector_store if services.retrieval_enabled else None,
        reranker=services.reranker,
        redis_client=services.redis_cache,
        domain=report_domain,
        min_confidence=0.6,
    )
    if services.indexer is not None:
        mapper.indexer = services.indexer
        mapper.bm25_index = services.indexer.bm25_index

    # Load alias resolver from the domain manifest for canonical field matching
    try:
        mapper.alias_resolver = await load_alias_resolver(db, domain_name=domain.name)
        logger.info(
            "[MAP] alias resolver loaded: domain=%s report_id=%s",
            report_domain,
            report_id,
        )
    except Exception as exc:
        logger.warning(
            "[MAP] alias resolver unavailable for report_id=%s domain=%s: %s — using raw labels",
            report_id,
            report_domain,
            exc,
            exc_info=True,
        )
        mapper.alias_resolver = AliasResolver.empty(report_domain)

    raw_results = await mapper.map_form(
        schema,
        universal_evidence,
        report_id=report_id,
        user_id=user_id,
        document_ids=await DocumentRepository(db).get_document_ids_for_report(
            report_id
        ),
    )

    handler = MappingHandler(mapper=mapper, evidence_store=None, registry=None)
    results, populated_schema = handler.build_results(
        raw_results, field_meta, form_schema, universal_evidence
    )

    # Save the *populated* (mapped) form schema so the frontend gets values
    await repo.save_form_schema(report_id, populated_schema)
    await repo.save_mapping_results(report_id, results)

    summary = handler.summarize_results(results)
    logger.info(
        "[MAP] run_mapping done: report_id=%s total=%d mapped=%d unmatched=%d "
        "by_method=%s",
        report_id,
        summary["total_fields"],
        summary["mapped"],
        summary["unmatched"],
        summary["by_method"],
    )
    if summary["unmatched"]:
        logger.info(
            "[MAP] UNMATCHED fields (%d) for report_id=%s: %s",
            summary["unmatched"],
            report_id,
            summary["unmatched_fields"],
        )
    return {
        "report_id": report_id,
        "session_id": session_id,
        "mappings": results,
        "populated_schema": populated_schema,
        "evidence_count": len(universal_evidence),
        "mapping_summary": summary,
    }
async def enqueue_intent_prepass(
    report, repo: ReportRepository, user_id: str, trigger_intent: bool = True
):
    if not trigger_intent:
        logger.info("[Intent] skipped (client opted out: report=%s)", report.id)
        return None
    from inspection_ai.tasks.intent_task import trigger_intent_task

    job = await repo.create_job(report.id, user_id, "intent")
    try:
        trigger_intent_task.delay(str(job.id), report.id, user_id)
        logger.info("[Intent] job %s queued: report_id=%s", job.id, report.id)
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "[Intent] broker unavailable, leaving for map fallback (report=%s): %s",
            report.id,
            e,
        )
    return job
async def require_report_lock(
    report_id: str, db: AsyncSession, user_id: str, lock_token: str = None
):
    """Verify a mutating operation holds a valid (unexpired) lock for the user.

    Only interactive mutations (upload / scan / map) require the lock — case
    the warning level by whether the lock exists at all (it must, to avoid two
    users mutating the same shared report simultaneously). Raises HTTP 409 with
    holder info when the lock is missing, held by another user, or stale.
    """
    doc_repo = DocumentRepository(db)
    lock = await doc_repo.get_lock(report_id)
    if lock is None:
        raise HTTPException(
            status_code=409,
            detail="Report is not locked — acquire a lock before processing",
        )
    now = datetime.utcnow()
    if (
        lock.expires_at is not None
        and lock.expires_at < now
        and not lock.mapping_in_progress
    ):
        # Stale lock: another user may (re)acquire; this caller should re-acquire.
        raise HTTPException(
            status_code=409,
            detail="Report lock has expired — please re-acquire before processing",
        )
    if lock.locked_by != user_id or (lock_token and lock.lock_token != lock_token):
        holder_name = await ReportRepository(db).get_user_email(lock.locked_by or "")
        raise HTTPException(
            status_code=409,
            detail={
                "locked_by_user": holder_name,
                "locked_by": lock.locked_by,
                "expires_at": (
                    lock.expires_at.isoformat() if lock.expires_at else None
                ),
                "message": "Report is locked by another user",
            },
        )
    return lock
def parse_doc_types(doc_types_raw: str, file_count: int) -> list:
    if not doc_types_raw:
        raise HTTPException(
            status_code=400, detail="doc_types is required for PDF upload"
        )
    try:
        doc_types_list = json.loads(doc_types_raw)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=400, detail="doc_types must be a valid JSON array"
        ) from e

    if not isinstance(doc_types_list, list):
        raise HTTPException(status_code=400, detail="doc_types must be a JSON array")

    if len(doc_types_list) != file_count:
        raise HTTPException(
            status_code=400,
            detail=f"Files count ({file_count}) does not match doc_types count ({len(doc_types_list)})",
        )

    allowed_types = {"scanned", "handwritten"}
    parsed = []
    for item in doc_types_list:
        if not isinstance(item, str):
            raise HTTPException(
                status_code=400,
                detail=f"doc_types must be an array of strings, got item: {item}",
            )
        doc_type = item.strip().lower()
        if doc_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid doc_type: {item} (must be one of {sorted(allowed_types)})",
            )
        parsed.append(doc_type)
    return parsed
PIPELINE_WORKERS = 3
MODAL_CONCURRENCY = 3
async def run_pipeline(
    pipeline_files: list,
    extractor,
    repo,
    report_id: str,
    session_id: str,
    batch_id: str,
    user_id: str,
    all_file_records: list,
    semaphore: asyncio.Semaphore,
):
    loop = asyncio.get_running_loop()
    is_async_extractor = inspect.iscoroutinefunction(extractor.extract)
    executor = (
        None if is_async_extractor else ThreadPoolExecutor(max_workers=PIPELINE_WORKERS)
    )

    async def process_one(vf: UploadedFile):
        content_hash = hashlib.sha256(vf.content).hexdigest()
        file = await repo.create_file(
            report_id=report_id,
            filename=vf.filename,
            mime_type=vf.content_type,
            file_hash=content_hash,
            file_size=len(vf.content),
            storage_path=str(UPLOAD_DIR / report_id / vf.filename),
            uploaded_by=user_id,
        )
        await repo.update_file_extraction_state(file.id, "processing")
        all_file_records.append(file)
        logger.info(
            "[UPLOAD] Processing file: file_id=%s filename=%s report_id=%s batch_id=%s async=%s",
            file.id,
            vf.filename,
            report_id,
            batch_id,
            is_async_extractor,
        )

        if is_async_extractor:
            async with semaphore:
                evidence = await extractor.extract(
                    file.id,
                    vf.content,
                    report_id,
                    session_id,
                    batch_id,
                    filename=vf.filename,
                    user_id=user_id,
                    document_id=getattr(vf, "document_id", None),
                )
        else:
            evidence = await loop.run_in_executor(
                executor,
                partial(
                    extractor.extract,
                    file.id,
                    vf.content,
                    report_id,
                    session_id,
                    batch_id,
                    filename=vf.filename,
                    user_id=user_id,
                    document_id=getattr(vf, "document_id", None),
                ),
            )

        await repo.add_evidence(
            batch_id,
            report_id,
            file.id,
            evidence,
            user_id=user_id,
        )
        await repo.update_file_extraction_state(file.id, "completed")
        return file, evidence

    try:
        results = await asyncio.gather(*(process_one(vf) for vf in pipeline_files))
    finally:
        if executor is not None:
            executor.shutdown(wait=True)
    return results
