import asyncio
import hashlib
import inspect
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import List

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    UploadFile,
    status,
)
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from inspection_ai.api.auth.security import get_current_user
from inspection_ai.api.schemas import DocumentInfo, ReportDetail
from inspection_ai.database.base import get_db
from inspection_ai.database.models.evidence import MappingResult
from inspection_ai.database.models.report import ReportStatus
from inspection_ai.database.models.user import OrganizationMember, User, UserRole
from inspection_ai.database.repositories.document_repository import DocumentRepository
from inspection_ai.database.repositories.report_repository import ReportRepository
from inspection_ai.database.repositories.user_repository import UserRepository
from inspection_ai.tasks.pdf_task import process_pdf_task
from inspection_ai.universal_service.api.mapping_handler import MappingHandler
from inspection_ai.universal_service.api.upload_handler import (
    UniversalUploadHandler,
    UploadedFile,
)
from inspection_ai.ai.extraction.handwritten_extractor import (
    HandwrittenExtractor,
)
from inspection_ai.ai.extraction.image_extractor import ImageExtractor
from inspection_ai.ai.extraction.pdf_extractor import PDFExtractor
from inspection_ai.ai.mapping.alias_resolver import (
    AliasResolver,
    load_alias_resolver,
)
from inspection_ai.ai.mapping.form_schema_adapter import (
    normalize_form_schema,
)
from inspection_ai.ai.mapping.universal_mapper import (
    UniversalMapper,
)
from inspection_ai.ai.models.evidence import (
    Evidence as UniversalEvidence,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])

upload_handler = UniversalUploadHandler()
UPLOAD_DIR = Path("./storage/uploads")

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp"}


class ReportResponse(BaseModel):
    report_id: str
    session_id: str = None
    status: str
    file_count: int = 0
    created_at: str = None
    created: bool = False
    linked: bool = False
    restored: bool = False


class MappingPayload(BaseModel):
    form_schema: dict = None
    # The frontend selects a domain by NAME (the extension's domain selector is
    # name-based), so /map accepts either an explicit integer id or a name and
    # resolves to the id before running. This removes id-coupling on the client
    # and lets a missing/unknown selector fall back to the default domain.
    domain_id: int = None
    domain: str = None


class FormSchemaPayload(BaseModel):
    form_schema: dict
    scanned_payload: dict = None
    trigger_intent: bool = True
    source_url: str  # Required - website URL of the report being scanned
    source_domain: str = "openquire"


class CreateReportRequest(BaseModel):
    source_url: str = None
    source_domain: str = "openquire"


# Intent pre-pass is opt-in per form-schema upload: the client (extension)
# decides whether the report page should trigger the LLM intent pre-pass, so
# the backend holds no platform-specific URL knowledge.


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
    from inspection_ai.universal_service.api.dependencies import (
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


@router.post("/link", response_model=ReportResponse)
async def link_report(
    payload: CreateReportRequest = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = ReportRepository(db)
    doc_repo = DocumentRepository(db)
    org_id = await resolve_organization(db, current_user)

    created = False
    linked = False
    restored = False
    source_url = (payload.source_url or "").strip() if payload else ""
    source_domain = (payload.source_domain if payload else None) or "openquire"

    if source_url:
        # Resolve the single shared report for this URL and link the user —
        # dedup + soft-delete restore handled atomically inside the repo.
        report, created, restored, linked = await repo.get_or_create_report_by_url(
            org_id, source_url, current_user.id, source_domain
        )
    else:
        # No URL -> cannot dedup, always create a new report
        report = await repo.create_report(current_user.id, org_id)
        created = True
        _, linked = await doc_repo.link_user_report(report.id, current_user.id)

    logger.info(
        "[LINK] report=%s user=%s created=%s linked=%s restored=%s",
        report.id,
        current_user.id,
        created,
        linked,
        restored,
    )
    return ReportResponse(
        report_id=report.id,
        session_id=report.session_id,
        status=report.status.value,
        created_at=report.created_at.isoformat() if report.created_at else None,
        created=created,
        linked=linked,
        restored=restored,
    )


# --------------------------------------------------------------------------- #
# Report locks (shared reports: only one user processes interactively at a time)
# --------------------------------------------------------------------------- #


class LockPayload(BaseModel):
    lock_token: str = None


@router.post("/{report_id}/lock")
async def acquire_report_lock(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = ReportRepository(db)
    doc_repo = DocumentRepository(db)
    report = await repo.get_report_for_user(report_id, current_user.id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.deleted_at is not None:
        raise HTTPException(status_code=409, detail="Report is deleted")

    result = await doc_repo.acquire_lock(report_id, current_user.id)
    if result["status"] == "held":
        locked_by_name = await repo.get_user_email(result.get("locked_by") or "")
        raise HTTPException(
            status_code=409,
            detail={
                "locked_by_user": locked_by_name,
                "locked_by": result.get("locked_by"),
                "expires_at": result.get("expires_at"),
                "message": "Report is locked by another user",
            },
        )
    return {
        "status": "acquired",
        "report_id": report_id,
        "lock_token": result.get("lock_token"),
        "expires_at": result.get("expires_at"),
    }


@router.post("/{report_id}/lock/heartbeat")
async def heartbeat_report_lock(
    report_id: str,
    payload: LockPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc_repo = DocumentRepository(db)
    ok = await doc_repo.heartbeat_lock(
        report_id, current_user.id, payload.lock_token or ""
    )
    if not ok:
        raise HTTPException(status_code=409, detail="Lock is not held by this user")
    lock = await doc_repo.get_lock(report_id)
    return {
        "status": "ok",
        "report_id": report_id,
        "expires_at": lock.expires_at.isoformat() if lock else None,
    }


@router.post("/{report_id}/unlock")
async def release_report_lock(
    report_id: str,
    payload: LockPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc_repo = DocumentRepository(db)
    ok = await doc_repo.release_lock(
        report_id, current_user.id, payload.lock_token or ""
    )
    return {"status": "ok" if ok else "not_held", "report_id": report_id}


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


# Number of worker threads used per pipeline (scanned / handwritten).
# Each worker processes one PDF at a time; increasing this raises the level of
# file-level parallelism but also the load on the LLM / docling backends.
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


@router.post("/{report_id}/upload/pdf")
async def upload_pdf(
    report_id: str,
    files: list[UploadFile] = File(...),
    doc_types: str = Form(...),
    x_lock_token: str = Header(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # PDF upload endpoint entered ---------------------------------------------------
    logger.info(
        "[PDF] upload_pdf endpoint entered: report_id=%s user_id=%s files=%d",
        report_id,
        current_user.id,
        len(files),
    )
    repo = ReportRepository(db)
    report = await repo.get_report_for_user(report_id, current_user.id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    # Interactive mutation on a shared report -> lock required
    await require_report_lock(report_id, db, current_user.id, x_lock_token)
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    doc_type_list = parse_doc_types(doc_types, len(files))
    logger.info(
        "[PDF] Doc types parsed: report_id=%s scanned=%d handwritten=%d",
        report_id,
        sum(1 for d in doc_type_list if d == "scanned"),
        sum(1 for d in doc_type_list if d == "handwritten"),
    )

    validated = []
    for f in files:
        if not f.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400, detail="Only PDF files allowed: " + f.filename
            )
        content = f.file.read()
        validated.append(UploadedFile(f.filename, content, "application/pdf"))

    # Global knowledge-base dedup: the same content uploaded by ANY user to
    # ANY report is stored and extracted exactly once. Subsequent uploads only
    # create a report_documents link (and a File row for the report read-back).
    doc_repo = DocumentRepository(db)
    deduped = []  # (vf, doc_type) pairs that need extraction
    linked_docs = 0
    for vf, dt in zip(validated, doc_type_list):
        content_hash = hashlib.sha256(vf.content).hexdigest()
        doc = await doc_repo.get_document_by_hash(content_hash)
        if doc is not None:
            # Knowledge-base hit -> link only, never re-extract
            await doc_repo.link_document_report(doc.id, report.id, current_user.id)
            linked_docs += 1
            existing_file = await repo.get_file_by_hash(report.id, content_hash)
            if existing_file is None:
                file = await repo.create_file(
                    report_id=report.id,
                    filename=vf.filename,
                    doc_type=dt,
                    file_hash=content_hash,
                    file_size=len(vf.content),
                    mime_type="application/pdf",
                    storage_path=doc.storage_path or "",
                    uploaded_by=current_user.id,
                )
                # Extraction already exists for this document
                await repo.update_file_extraction_state(file.id, "completed")
            logger.info(
                "[PDF] knowledge-base hit: doc=%s linked to report=%s (no re-extraction)",
                doc.id,
                report_id,
            )
            continue
        # New document -> register globally and extract once
        try:
            doc = await doc_repo.create_document(
                content_hash=content_hash,
                filename=vf.filename,
                mime_type="application/pdf",
                file_size=len(vf.content),
                doc_type=dt,
                created_by=current_user.id,
            )
        except Exception:
            # Lost an insert race against a concurrent upload of the same
            # content to a DIFFERENT report -> fall back to linking.
            doc = await doc_repo.get_document_by_hash(content_hash)
            if doc is None:
                raise
            await doc_repo.link_document_report(doc.id, report.id, current_user.id)
            linked_docs += 1
            continue
        await doc_repo.link_document_report(doc.id, report.id, current_user.id)
        vf.document_id = doc.id  # carried into the extraction pipelines
        deduped.append((vf, dt))

    validated = [item[0] for item in deduped]
    doc_type_list = [item[1] for item in deduped]
    if not validated:
        if linked_docs:
            return {
                "status": "linked",
                "report_id": report_id,
                "linked_documents": linked_docs,
                "message": "All documents already exist in the knowledge base; linked to this report without re-extraction.",
            }
        raise HTTPException(
            status_code=400, detail="All provided files were already uploaded"
        )

    # Create a tracking job.  When a broker is reachable we hand off to Celery
    # and return immediately; otherwise we fall back to inline processing so the
    # API still works without Redis running (useful for local dev / first deploy).
    job = await repo.create_job(report_id, current_user.id, "pdf")
    enqueued = False
    try:
        # Write PDFs to a path shared with the Celery worker container (both
        # mount .:/app).  ``tempfile.mkdtemp`` would land in the API container's
        # private /tmp, which the separate worker container cannot read.
        work_dir = UPLOAD_DIR / "jobs" / str(job.id)
        work_dir.mkdir(parents=True, exist_ok=True)
        entries = []
        for vf, dt in zip(validated, doc_type_list):
            dest = work_dir / vf.filename
            dest.write_bytes(vf.content)
            content_hash = hashlib.sha256(vf.content).hexdigest()
            # Record the canonical storage path on the knowledge-base document
            if getattr(vf, "document_id", None):
                stored_doc = await doc_repo.get_document(vf.document_id)
                if stored_doc is not None and not stored_doc.storage_path:
                    stored_doc.storage_path = str(dest)
                    await db.commit()
            # Persist a File row so the report read‑back shows the document
            file = await repo.create_file(
                report_id=report.id,
                filename=vf.filename,
                doc_type=dt,
                file_hash=content_hash,
                file_size=len(vf.content),
                mime_type="application/pdf",
                storage_path=str(UPLOAD_DIR / report_id / vf.filename),
                uploaded_by=current_user.id,
            )
            await repo.update_file_extraction_state(file.id, "processing")
            entries.append(
                {
                    "path": str(dest),
                    "filename": vf.filename,
                    "doc_type": dt,
                    "file_id": file.id,
                    "document_id": getattr(vf, "document_id", None),
                }
            )

        process_pdf_task.delay(str(job.id), entries, report_id, current_user.id)
        enqueued = True
        logger.info(
            "[PDF] job %s queued (Celery): report_id=%s files=%d",
            job.id,
            report_id,
            len(files),
        )
        return {
            "status": "processing",
            "job_id": job.id,
            "report_id": report_id,
            "file_count": len(validated),
        }
    except Exception as broker_error:  # noqa: BLE001
        if enqueued:
            # enqueued before the exception surfaced -> unlikely; treat as failed
            await repo.update_job_status(job.id, "failed", str(broker_error))
            raise HTTPException(status_code=500, detail=str(broker_error))
        logger.warning(
            "[PDF] broker unavailable; processing inline (job=%s): %s",
            job.id,
            broker_error,
        )
        await repo.update_job_status(job.id, "processing")

    await repo.set_report_status(report_id, ReportStatus.processing)
    batch = await repo.create_batch(report_id)

    services = get_services()
    vector_store = services.vector_store
    scanned_extractor = PDFExtractor(
        vector_store=vector_store, modal_executor=services.modal_executor
    )
    handwritten_extractor = HandwrittenExtractor(
        llm_client=services.llm, vector_store=vector_store
    )

    # Partition files into handwritten and scanned collections based on the
    # caller-supplied ``doc_types`` array. Order within each list preserves the
    # original index so downstream aggregations stay deterministic.
    handwritten_files = [
        vf for vf, dt in zip(validated, doc_type_list) if dt == "handwritten"
    ]
    scanned_files = [vf for vf, dt in zip(validated, doc_type_list) if dt == "scanned"]
    logger.info(
        "[PDF] Pipelines starting: report_id=%s batch_id=%s scanned=%d handwritten=%d concurrency=%d",
        report_id,
        batch.id,
        len(scanned_files),
        len(handwritten_files),
        MODAL_CONCURRENCY,
    )

    file_records: list = []
    total_evidence = 0
    semaphore = asyncio.Semaphore(MODAL_CONCURRENCY)
    try:
        # Run both pipelines concurrently. Each pipeline is internally parallel
        # via its own ThreadPoolExecutor (see ``run_pipeline``), so multiple
        # PDFs within a collection are processed in parallel batches.
        scanned_results, handwritten_results = await asyncio.gather(
            run_pipeline(
                scanned_files,
                scanned_extractor,
                repo,
                report_id,
                report.session_id,
                batch.id,
                current_user.id,
                file_records,
                semaphore,
            ),
            run_pipeline(
                handwritten_files,
                handwritten_extractor,
                repo,
                report_id,
                report.session_id,
                batch.id,
                current_user.id,
                file_records,
                semaphore,
            ),
        )

        total_evidence = sum(len(ev) for _, ev in scanned_results) + sum(
            len(ev) for _, ev in handwritten_results
        )
        logger.info(
            "[PDF] Extraction finished: report_id=%s scanned_files=%d handwritten_files=%d total_evidence=%d",
            report_id,
            len(scanned_results),
            len(handwritten_results),
            total_evidence,
        )

        await repo.complete_batch(batch.id, total_evidence)
        await repo.set_report_status(report_id, ReportStatus.completed)
        await repo.update_job_status(job.id, "completed")
        logger.info(
            "[PDF] Upload SUCCESS (before return): report_id=%s user_id=%s files=%d batch_id=%s evidence=%d",
            report_id,
            current_user.id,
            len(file_records),
            batch.id,
            total_evidence,
        )
        return {
            "report_id": report_id,
            "file_count": len(file_records),
            "evidence_count": total_evidence,
            "files": [
                {"file_id": f.id, "filename": f.filename, "status": f.status.value}
                for f in file_records
            ],
            "status": "Completed",
        }
    except Exception as e:  # noqa: BLE001
        for f in file_records:
            try:
                await repo.update_file_extraction_state(f.id, "failed", str(e))
            except Exception:  # noqa: BLE001
                pass
        await repo.set_report_status(report_id, ReportStatus.failed, str(e))
        await repo.update_job_status(job.id, "failed", str(e))
        logger.error(
            "[PDF] Upload FAILED (before return): report_id=%s user_id=%s batch_id=%s files=%d error=%s",
            report_id,
            current_user.id,
            batch.id,
            len(file_records),
            e,
            exc_info=True,
        )
        return {
            "report_id": report_id,
            "file_count": len(file_records),
            "evidence_count": total_evidence,
            "files": [
                {"file_id": f.id, "filename": f.filename, "status": f.status.value}
                for f in file_records
            ],
            "status": "failed",
        }


@router.post("/{report_id}/upload/image")
async def upload_image(
    report_id: str,
    files: list[UploadFile] = File(...),
    x_lock_token: str = Header(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    image_items = []

    # Image upload endpoint entered -------------------------------------------------
    logger.info(
        "[IMAGE] upload_image endpoint entered: report_id=%s user_id=%s files=%d",
        report_id,
        current_user.id,
        len(files),
    )
    repo = ReportRepository(db)
    report = await repo.get_report_for_user(report_id, current_user.id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    # Interactive mutation on a shared report -> lock required
    await require_report_lock(report_id, db, current_user.id, x_lock_token)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    for f in files:
        if f.filename is None:
            raise HTTPException(status_code=400, detail="Missing filename")
        low = Path(f.filename).suffix.lower()
        if low == ".zip":
            zip_bytes = f.file.read()
            for name, content in upload_handler.extract_zip_entries(zip_bytes):
                if Path(name).suffix.lower() in IMAGE_EXTENSIONS:
                    image_items.append((name, content))
                else:
                    logger.info(
                        "[IMAGE] skipping non-image entry in zip: file=%s report=%s",
                        name,
                        report_id,
                    )
        elif low in IMAGE_EXTENSIONS:
            image_items.append((f.filename, f.file.read()))
        else:
            raise HTTPException(
                status_code=400, detail="Invalid image/zip file: " + f.filename
            )

    logger.info(
        "[IMAGE] Files validated: report_id=%s user_id=%s raw_files=%d resolved_images=%d",
        report_id,
        current_user.id,
        len(files),
        len(image_items),
    )

    if not image_items:
        raise HTTPException(status_code=400, detail="No valid image files provided")

    # Global knowledge-base dedup: the same image content (by hash) uploaded by
    # ANY user to ANY report is stored/extracted once; other uploads only link.
    doc_repo = DocumentRepository(db)
    deduped = []  # (filename, content) needing extraction
    linked_docs = 0
    for filename, content in image_items:
        if isinstance(content, str):
            content = content.encode("utf-8")
        content_hash = hashlib.sha256(content).hexdigest()
        doc = await doc_repo.get_document_by_hash(content_hash)
        if doc is not None:
            await doc_repo.link_document_report(doc.id, report.id, current_user.id)
            linked_docs += 1
            existing_file = await repo.get_file_by_hash(report.id, content_hash)
            if existing_file is None:
                file = await repo.create_file(
                    report_id=report.id,
                    filename=filename,
                    doc_type="image",
                    file_size=len(content),
                    file_hash=content_hash,
                    mime_type="image/" + Path(filename).suffix.lstrip(".") or "jpeg",
                    storage_path=doc.storage_path or "",
                    uploaded_by=current_user.id,
                )
                await repo.update_file_extraction_state(file.id, "completed")
            logger.info(
                "[IMAGE] knowledge-base hit: doc=%s linked to report=%s (no re-extraction)",
                doc.id,
                report_id,
            )
            continue
        try:
            doc = await doc_repo.create_document(
                content_hash=content_hash,
                filename=filename,
                mime_type="image/" + Path(filename).suffix.lstrip(".") or "jpeg",
                file_size=len(content),
                doc_type="image",
                created_by=current_user.id,
            )
        except Exception:
            # Lost an insert race on the same content in another report
            doc = await doc_repo.get_document_by_hash(content_hash)
            if doc is None:
                raise
            await doc_repo.link_document_report(doc.id, report.id, current_user.id)
            linked_docs += 1
            continue
        await doc_repo.link_document_report(doc.id, report.id, current_user.id)
        deduped.append((filename, content, doc))

    image_items = [(f, c) for f, c, _ in deduped]
    if not image_items:
        if linked_docs:
            return {
                "status": "linked",
                "report_id": report_id,
                "linked_documents": linked_docs,
                "message": "All images already exist in the knowledge base; linked to this report without re-extraction.",
            }
        raise HTTPException(
            status_code=400, detail="All provided images were already uploaded"
        )

    # Create a tracking job.  Hand off to Celery when a broker is available,
    # otherwise process inline so the API works without Redis running.
    job = await repo.create_job(report_id, current_user.id, "image")
    enqueued = False
    try:
        # Write images to a path shared with the Celery worker container (both
        # mount .:/app), so the worker can read them back across containers.
        work_dir = UPLOAD_DIR / "jobs" / str(job.id)
        work_dir.mkdir(parents=True, exist_ok=True)
        entries = []
        for filename, content in image_items:
            if isinstance(content, str):
                content = content.encode("utf-8")

            content_hash = hashlib.sha256(content).hexdigest()
            dest = work_dir / filename
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(content)
            # Record the canonical storage path on the knowledge-base document
            entry_doc = next((doc for f, c, doc in deduped if f == filename), None)
            if entry_doc is not None and not entry_doc.storage_path:
                entry_doc.storage_path = str(dest)
                await db.commit()
            # Persist a File row so the report read‑back shows the document
            file = await repo.create_file(
                report_id=report.id,
                filename=filename,
                doc_type="image",
                file_size=len(content),
                file_hash=content_hash,
                mime_type="image/" + Path(filename).suffix.lstrip(".") or "jpeg",
                storage_path=str(UPLOAD_DIR / report_id / filename),
                uploaded_by=current_user.id,
            )
            await repo.update_file_extraction_state(file.id, "processing")
            entries.append(
                {
                    "path": str(dest),
                    "filename": filename,
                    "file_id": file.id,
                    "document_id": next(
                        (doc.id for f, c, doc in deduped if f == filename),
                        None,
                    ),
                }
            )
        from inspection_ai.tasks.image_task import process_image_task

        process_image_task.delay(str(job.id), entries, report_id, current_user.id)
        enqueued = True
        logger.info(
            "[IMAGE] job %s queued (Celery): report_id=%s images=%d",
            job.id,
            report_id,
            len(image_items),
        )
        return {
            "status": "processing",
            "job_id": job.id,
            "report_id": report_id,
            "file_count": len(image_items),
        }
    except Exception as broker_error:  # noqa: BLE001
        if enqueued:
            await repo.update_job_status(job.id, "failed", str(broker_error))
            raise HTTPException(status_code=500, detail=str(broker_error))
        logger.warning(
            "[IMAGE] broker unavailable; processing inline (job=%s): %s",
            job.id,
            broker_error,
        )
        await repo.update_job_status(job.id, "processing")

    await repo.set_report_status(report_id, ReportStatus.processing)
    batch = await repo.create_batch(report_id)

    services = get_services()
    extractor = ImageExtractor(
        llm_client=services.llm,
        config=services.config,
        vector_store=services.vector_store,
    )
    logger.info(
        "[IMAGE] ImageExtractor initialized: report_id=%s batch_id=%s images=%d vector_store=%s",
        report_id,
        batch.id,
        len(image_items),
        services.vector_store is not None,
    )

    loop = asyncio.get_running_loop()
    executor = ThreadPoolExecutor(max_workers=PIPELINE_WORKERS)
    file_records = []
    total_evidence = 0
    try:
        results = await loop.run_in_executor(executor, extractor.extract, image_items)
        logger.info(
            "[IMAGE] Extraction complete: report_id=%s batch_id=%s results=%d",
            report_id,
            batch.id,
            len(results),
        )

        for res in results:
            file = await repo.create_file(
                report_id=report_id,
                filename=res["filename"],
                mime_type="image/jpeg",
                file_hash=res["content_hash"],
                file_size=res["size"],
                storage_path=str(UPLOAD_DIR / report_id / res["filename"]),
                uploaded_by=current_user.id,
            )
            await repo.update_file_extraction_state(file.id, "processing")
            file_records.append(file)
            logger.info(
                "[IMAGE] File record created: file_id=%s report_id=%s filename=%s",
                file.id,
                report_id,
                res["filename"],
            )

            evidence = extractor.to_evidence(
                [res],
                file.id,
                report_id,
                report.session_id,
                batch.id,
                current_user.id,
                # filename -> knowledge-base document id
                {
                    res["filename"]: next(
                        (doc.id for f, c, doc in deduped if f == res["filename"]),
                        None,
                    )
                },
            )
            await repo.add_evidence(
                batch.id,
                report_id,
                file.id,
                evidence,
                current_user.id,
            )
            total_evidence += len(evidence)
            await repo.update_file_extraction_state(file.id, "completed")
            logger.info(
                "[IMAGE] File completed: file_id=%s report_id=%s filename=%s evidence=%d",
                file.id,
                report_id,
                res["filename"],
                len(evidence),
            )

        document_ids = {f: doc.id for f, c, doc in deduped}
        await extractor.save_embeddings(
            results, report_id, current_user.id, document_ids
        )
        await repo.complete_batch(batch.id, total_evidence)
        await repo.set_report_status(report_id, ReportStatus.completed)
        await repo.update_job_status(job.id, "completed")
        logger.info(
            "[IMAGE] Upload SUCCESS: report_id=%s batch_id=%s files=%d evidence=%d",
            report_id,
            batch.id,
            len(file_records),
            total_evidence,
        )

        return {
            "report_id": report_id,
            "file_count": len(file_records),
            "evidence_count": total_evidence,
            "files": [
                {"file_id": f.id, "filename": f.filename, "status": f.status.value}
                for f in file_records
            ],
            "status": "Completed",
        }
    except Exception as e:  # noqa: BLE001
        for f in file_records:
            await repo.update_file_extraction_state(f.id, "failed", str(e))
        await repo.set_report_status(report_id, ReportStatus.failed, str(e))
        await repo.update_job_status(job.id, "failed", str(e))
        logger.error(
            "[IMAGE] Upload FAILED: report_id=%s batch_id=%s files=%d error=%s",
            report_id,
            batch.id,
            len(file_records),
            e,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        executor.shutdown(wait=True)


@router.post("/{report_id}/map")
async def map_report_fields(
    report_id: str,
    payload: MappingPayload,
    x_lock_token: str = Header(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = ReportRepository(db)
    doc_repo = DocumentRepository(db)
    report = await repo.get_report_for_user(report_id, current_user.id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    # Interactive mutation -> lock required, and hold it for the whole run so
    # the lock cannot expire (and be taken over) mid-map (GAP 5).
    await require_report_lock(report_id, db, current_user.id, x_lock_token)
    await doc_repo.set_mapping_in_progress(report_id, True)

    # If the caller supplies a form schema, persist it before mapping.
    if payload.form_schema:
        await repo.save_form_schema(report_id, payload.form_schema)

    if not (await repo.get_form_schema_for_report(report_id)):
        await doc_repo.set_mapping_in_progress(report_id, False)
        raise HTTPException(status_code=400, detail="No form schema found for report")

    domain_id = payload.domain_id
    # Resolve the domain from the name when the client sends a name (the
    # extension's domain selector is name-based) instead of an integer id.
    if domain_id is None and payload.domain:
        from inspection_ai.database.models.domain import Domain

        dom_result = await db.execute(
            select(Domain).where(
                func.lower(Domain.name) == func.lower(payload.domain),
                Domain.is_active == 1,
            )
        )
        dom = dom_result.scalar_one_or_none()
        domain_id = dom.id if dom is not None else None
    logger.info(
        "[MAP] map_report_fields: report_id=%s domain_id=%s domain_name=%s user=%s",
        report_id,
        domain_id,
        payload.domain,
        current_user.id,
    )

    try:
        result = await run_mapping(report_id, current_user.id, db, domain_id=domain_id)
        logger.info(
            "[MAP] mapping complete: report_id=%s mapped=%d",
            report_id,
            len(result.get("mappings", [])),
        )
        return {
            "status": "completed",
            "report_id": report_id,
            "mappings": result["mappings"],
            "populated_schema": result["populated_schema"],
            "evidence_count": result.get("evidence_count", 0),
        }
    except Exception as exc:
        logger.error(
            "[MAP] mapping failed: report_id=%s error=%s",
            report_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        await doc_repo.set_mapping_in_progress(report_id, False)


@router.post("/{report_id}/form_schema")
async def store_form_schema(
    report_id: str,
    payload: FormSchemaPayload,
    x_lock_token: str = Header(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = ReportRepository(db)
    report = await repo.get_report_for_user(report_id, current_user.id)

    if report is None:
        # The caller is not yet linked to the report in the path. Resolve the
        # single shared report for this URL and link the user — this must NEVER
        # auto-create an orphan row (fresh UUID, no ReportUser link) or the very
        # next call (map/upload/mapping) will 404 for this user.
        org_id = await resolve_organization(db, current_user)
        url = (payload.source_url or "").strip()
        report, _created, _restored, linked = await repo.get_or_create_report_by_url(
            org_id, url or "", current_user.id, payload.source_domain or "openquire"
        )
        logger.info(
            "[FORMSchema] Resolved report %s for user %s url=%r linked=%s",
            report.id,
            current_user.id,
            payload.source_url,
            linked,
        )
    else:
        # Interactive mutation on an existing (shared) report -> lock required.
        await require_report_lock(report_id, db, current_user.id, x_lock_token)
    if not payload.form_schema:
        raise HTTPException(status_code=400, detail="form_schema is required")

    await repo.save_form_schema(report.id, payload.form_schema, payload.scanned_payload)
    intent_job = None

    if payload.trigger_intent:
        intent_job = await enqueue_intent_prepass(
            report, repo, current_user.id, trigger_intent=payload.trigger_intent
        )

    return {
        "report_id": report.id,
        "status": "stored",
        "intent_triggered": intent_job is not None,
    }


@router.get("/{report_id}/form_schema")
async def get_form_schema(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = ReportRepository(db)
    report = await repo.get_report_for_user(report_id, current_user.id)

    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    fs = await repo.get_form_schema_for_report(report_id)

    if fs is None:
        raise HTTPException(status_code=404, detail="No form schema found")

    return {
        "report_id": report_id,
        "form_schema": fs.schema_json,
        "scanned_payload": fs.scanned_payload,
        "version": fs.version,
    }


@router.put("/{report_id}/form_schema")
async def update_form_schema(
    report_id: str,
    payload: FormSchemaPayload,
    x_lock_token: str = Header(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update (re-scan) a report's stored form schema.

    Unlike POST this never auto-resolves/creates a report — the report must
    already exist and the caller must be linked to it. An interactive mutation,
    so the report lock is required.
    """
    repo = ReportRepository(db)
    report = await repo.get_report_for_user(report_id, current_user.id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    await require_report_lock(report_id, db, current_user.id, x_lock_token)
    if not payload.form_schema:
        raise HTTPException(status_code=400, detail="form_schema is required")

    await repo.save_form_schema(report.id, payload.form_schema, payload.scanned_payload)
    return {
        "report_id": report.id,
        "status": "updated",
        "message": "Form schema updated",
    }


@router.get("/{report_id}/mapping")
async def get_mapping_results(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = ReportRepository(db)
    report = await repo.get_report_for_user(report_id, current_user.id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    rows = (
        (
            await db.execute(
                select(MappingResult).where(MappingResult.report_id == report_id)
            )
        )
        .scalars()
        .all()
    )
    mappings = [
        {
            "field_id": r.field_id,
            "field_name": r.field_name,
            "value": r.value,
            "confidence": r.confidence,
            "option_id": r.option_id,
            "sources": r.sources,
            "mapping_method": r.mapping_method,
        }
        for r in rows
    ]
    fs = await repo.get_form_schema_for_report(report_id)
    processing = await repo.get_report_processing_status(report_id)
    return {
        "report_id": report_id,
        "mappings": mappings,
        "populated_schema": fs.schema_json if fs else None,
        "processing": processing,
    }


@router.get("/user", response_model=List[ReportDetail])
async def get_user_reports(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all reports belonging to the authenticated user.

    NOTE: registered *before* the ``/{report_id}`` route so the literal path
    segment ``/user`` is never captured as a report id.
    """
    repo = ReportRepository(db)
    reports = await repo.get_reports_by_user(current_user.id)

    result = []
    for report in reports:
        # Load files for this report
        file_objs = await repo.get_files(report.id)

        # Load latest form schema
        fs_obj = await repo.get_form_schema_for_report(report.id)

        # Build document info list
        documents = [
            DocumentInfo(
                document_id=f.id,
                name=f.filename,
                size=f.file_size_bytes,
                type=f.mime_type,
                uploaded_at=f.created_at,
            )
            for f in file_objs
        ]

        # Build form schema dict if available
        form_schema_dict = None
        if fs_obj and fs_obj.schema_json:
            form_schema_dict = fs_obj.schema_json

        result.append(
            ReportDetail(
                created_by=report.created_by,
                report_id=report.id,
                report_url=report.source_url or "",
                report_name=None,
                domain=report.source_domain or "openquire",
                created_at=report.created_at,
                documents=documents,
                form_schema=form_schema_dict,
            )
        )

    return result


@router.get("/{report_id}", response_model=ReportDetail)
async def get_report(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = ReportRepository(db)
    report = await repo.get_report_for_user(report_id, current_user.id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    # Load files for this report
    file_objs = await repo.get_files(report_id)

    # Load latest form schema
    fs_obj = await repo.get_form_schema_for_report(report_id)

    # Build document info list
    documents = [
        DocumentInfo(
            document_id=f.id,
            name=f.filename,
            size=f.file_size_bytes,
            type=f.mime_type,
            uploaded_at=f.created_at,
        )
        for f in file_objs
    ]

    # Build form schema dict if available
    form_schema_dict = None
    if fs_obj and fs_obj.schema_json:
        form_schema_dict = fs_obj.schema_json

    return ReportDetail(
        created_by=report.created_by,
        report_id=report.id,
        report_url=report.source_url or "",
        report_name=None,
        domain=report.source_domain or "openquire",
        created_at=report.created_at,
        documents=documents,
        form_schema=form_schema_dict,
    )


@router.get("/jobs/{job_id}")
async def get_job_status(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the status of an async processing job."""
    repo = ReportRepository(db)
    job = await repo.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your job")
    return {
        "job_id": job.id,
        "report_id": job.report_id,
        "job_type": job.job_type,
        "status": job.status,
        "error": job.error,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    logger.info(
        "[DELETE] delete_report called: report_id=%s user_id=%s",
        report_id,
        current_user.id,
    )

    repo = ReportRepository(db)
    # Soft-delete (shared-knowledge-base model): the report is hidden from all
    # queries/access but its rows, evidence and Qdrant points are retained so a
    # user re-opening the same URL gets it restored. This is NOT a hard delete;
    # admin hard-purge is a separate endpoint.
    report = await repo.get_report(report_id)
    if report is None:
        logger.warning("[DELETE] Report not found: report_id=%s", report_id)
        raise HTTPException(status_code=404, detail="Report not found")

    await repo.soft_delete_report(report_id)
    logger.info("[DELETE] Report soft-deleted: report_id=%s", report_id)
    return None


@router.delete("/{report_id}/documents/{document_id}", status_code=status.HTTP_200_OK)
async def unlink_document_from_report(
    report_id: str,
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Remove a document from a report (unlink).
    # The document is NOT deleted while other reports still reference it — only
    # the ``report_documents`` association is removed. When this was the LAST
    # report linked to the document, the document is soft-deleted (evidence and
    # Qdrant points retained) so the knowledge base knows it is no longer in active use.

    repo = ReportRepository(db)
    doc_repo = DocumentRepository(db)

    report = await repo.get_report_for_user(report_id, current_user.id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    doc = await doc_repo.get_document(document_id)
    if doc is None or doc.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Document not found")

    removed = await doc_repo.unlink_document_report(document_id, report_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Document not linked to report")

    # Keep the report read-back (files) in sync with the unlink: remove the
    # per-report File row that mirrors this (report, document) association.
    await repo.delete_file_by_report_and_hash(report_id, doc.content_hash or "")

    # If this was the last link, the document has no active reports -> soft delete
    remaining = await doc_repo.get_document_report_ids(document_id)
    if not remaining:
        await doc_repo.soft_delete_document(document_id)
        logger.info(
            "[UNLINK] Document %s has no remaining report links; soft-deleted",
            document_id,
        )

    logger.info(
        "[UNLINK] report=%s document=%s user=%s links_remaining=%d",
        report_id,
        document_id,
        current_user.id,
        len(remaining),
    )
    return {
        "status": "unlinked",
        "document_id": document_id,
        "report_id": report_id,
        "links_remaining": len(remaining),
    }
