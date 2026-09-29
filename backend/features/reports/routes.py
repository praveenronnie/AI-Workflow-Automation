import asyncio
import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor
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
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.constants import IMAGE_EXTENSIONS
from backend.core.file_validation import validate_upload
from backend.database.models.user import User
from backend.core.paths import (
    UPLOAD_DIR,
    resolve_transport_path,
    to_transport_path,
)
from backend.database.base import get_db
from backend.database.models.evidence import MappingResult
from backend.database.models.report import File as FileRecord, ReportStatus
from backend.database.repositories.document_repository import DocumentRepository
from backend.database.repositories.report_repository import ReportRepository
from backend.features.auth.security import get_current_user
from backend.features.mapping.upload_handler import (
    UniversalUploadHandler,
    UploadedFile,
)
from backend.features.reports.payloads import (
    CreateReportRequest,
    FormSchemaPayload,
    LockPayload,
    MappingPayload,
    ReportResponse,
)
from backend.features.reports.service import (
    MODAL_CONCURRENCY,
    PIPELINE_WORKERS,
    enqueue_intent_prepass,
    get_services,
    parse_doc_types,
    require_report_lock,
    resolve_organization,
    run_mapping,
    run_pipeline,
)
from backend.features.schemas import DocumentInfo, ReportDetail
from backend.tasks.pdf_task import process_pdf_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])

upload_handler = UniversalUploadHandler()


# Intent pre-pass is opt-in per form-schema upload: the client (extension)
# decides whether the report page should trigger the LLM intent pre-pass, so
# the backend holds no platform-specific URL knowledge.


@router.post("/link", response_model=ReportResponse)
async def link_report(
    payload: CreateReportRequest = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = ReportRepository(db)
    doc_repo = DocumentRepository(db)
    # Capture the id BEFORE resolve_organization: on the org-creation race
    # path it rolls the session back, which would expire current_user's
    # attributes and make any later access raise MissingGreenlet.
    user_id = current_user.id
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
            org_id, source_url, user_id, source_domain
        )
    else:
        # No URL -> cannot dedup, always create a new report
        report = await repo.create_report(user_id, org_id)
        created = True
        _, linked = await doc_repo.link_user_report(report.id, user_id)

    logger.info(
        "[LINK] report=%s user=%s created=%s linked=%s restored=%s",
        report.id,
        user_id,
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
    if not ok:
        # Wrong token or not the holder — never acknowledge with 200.
        raise HTTPException(
            status_code=403, detail="Report lock not held by this token"
        )
    return {"status": "ok", "report_id": report_id}


# Number of worker threads used per pipeline (scanned / handwritten).
# Each worker processes one PDF at a time; increasing this raises the level of
# file-level parallelism but also the load on the LLM / docling backends.


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
        # Content sniffing: reject payloads whose bytes are not a real PDF
        # before registering/enqueueing them (plan item 1.2).
        validate_upload(f.filename, content, "pdf")
        validated.append(UploadedFile(f.filename, content, "application/pdf"))

    # ORG-SCOPED knowledge-base dedup (privacy wall): the same content is
    # stored and extracted once *per organization*. Subsequent uploads from
    # the same org only create a report_documents link; a hash from another
    # org must never resolve here.
    org_id = await resolve_organization(db, current_user)
    doc_repo = DocumentRepository(db)
    deduped = []  # (vf, doc_type) pairs that need extraction
    linked_docs = 0
    for vf, dt in zip(validated, doc_type_list):
        content_hash = hashlib.sha256(vf.content).hexdigest()
        # Serialize per-content creation within this process: two concurrent
        # requests racing to insert the same (org, hash) would otherwise trip
        # the asyncpg greenlet-torn-session after a failed flush.
        from backend.features.mapping.upload_handler import content_lock

        async with content_lock(org_id, content_hash):
            doc = await doc_repo.get_document_by_hash(content_hash, org_id=org_id)
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
            # New document -> register (org-scoped) and extract once.
            doc = await doc_repo.create_document(
                content_hash=content_hash,
                filename=vf.filename,
                mime_type="application/pdf",
                file_size=len(vf.content),
                doc_type=dt,
                created_by=current_user.id,
                org_id=org_id,
            )
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
            # Portable reference (repo-relative + forward slashes) so the
            # worker resolves the file on its own host — required when the
            # API runs natively on Windows while the worker runs in Docker.
            transport_path = to_transport_path(dest)
            # Record the canonical storage path on the knowledge-base document
            if getattr(vf, "document_id", None):
                stored_doc = await doc_repo.get_document(vf.document_id)
                if stored_doc is not None and not stored_doc.storage_path:
                    stored_doc.storage_path = transport_path
                    await db.commit()
            # Persist a File row so the report read‑back shows the document
            file = await repo.create_file(
                report_id=report.id,
                filename=vf.filename,
                doc_type=dt,
                file_hash=content_hash,
                file_size=len(vf.content),
                mime_type="application/pdf",
                storage_path=transport_path,
                uploaded_by=current_user.id,
            )
            await repo.update_file_extraction_state(file.id, "processing")
            entries.append(
                {
                    "path": transport_path,
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
    scanned_extractor = services.get_extractor("pdf")
    handwritten_extractor = services.get_extractor("handwritten")

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
        if len(files) > upload_handler.MAX_FILES_PER_REQUEST:
            raise HTTPException(
                status_code=400,
                detail="Max "
                + str(upload_handler.MAX_FILES_PER_REQUEST)
                + " files per request",
            )
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
            content = f.file.read()
            # Content sniffing: reject payloads that aren't real images
            validate_upload(f.filename, content, "image")
            image_items.append((f.filename, content))
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

    # ORG-SCOPED knowledge-base dedup (privacy wall): same image content is
    # stored/extracted once per organization; a hash from another org never
    # resolves here.
    org_id = await resolve_organization(db, current_user)
    doc_repo = DocumentRepository(db)
    deduped = []  # (filename, content) needing extraction
    linked_docs = 0
    for filename, content in image_items:
        if isinstance(content, str):
            content = content.encode("utf-8")
        content_hash = hashlib.sha256(content).hexdigest()
        # Serialize per-content creation (see PDF path): prevents the
        # (org, hash) unique-index insert race under concurrent uploads.
        from backend.features.mapping.upload_handler import content_lock

        mime = "image/" + (Path(filename).suffix.lstrip(".") or "jpeg")
        async with content_lock(org_id, content_hash):
            doc = await doc_repo.get_document_by_hash(content_hash, org_id=org_id)
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
                        mime_type=mime,
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
            doc = await doc_repo.create_document(
                content_hash=content_hash,
                filename=filename,
                mime_type=mime,
                file_size=len(content),
                doc_type="image",
                created_by=current_user.id,
                org_id=org_id,
            )
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
            # Portable reference (repo-relative + forward slashes) so the
            # worker resolves the file on its own host — required when the
            # API runs natively on Windows while the worker runs in Docker.
            transport_path = to_transport_path(dest)
            # Record the canonical storage path on the knowledge-base document
            entry_doc = next((doc for f, c, doc in deduped if f == filename), None)
            if entry_doc is not None and not entry_doc.storage_path:
                entry_doc.storage_path = transport_path
                await db.commit()
            # Persist a File row so the report read‑back shows the document
            file = await repo.create_file(
                report_id=report.id,
                filename=filename,
                doc_type="image",
                file_size=len(content),
                file_hash=content_hash,
                mime_type="image/" + (Path(filename).suffix.lstrip(".") or "jpeg"),
                storage_path=transport_path,
                uploaded_by=current_user.id,
            )
            await repo.update_file_extraction_state(file.id, "processing")
            entries.append(
                {
                    "path": transport_path,
                    "filename": filename,
                    "file_id": file.id,
                    "document_id": next(
                        (doc.id for f, c, doc in deduped if f == filename),
                        None,
                    ),
                }
            )
        from backend.tasks.image_task import process_image_task

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
    extractor = services.get_extractor("image")
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
                # The physical upload lives in the extraction work_dir; store
                # its portable reference so read-back resolves on any host.
                storage_path=to_transport_path(
                    UPLOAD_DIR / "jobs" / str(job.id) / res["filename"]
                ),
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
        from backend.database.models.domain import Domain

        dom_result = await db.execute(
            select(Domain).where(
                func.lower(Domain.name) == func.lower(payload.domain),
                Domain.is_active == 1,
            )
        )
        dom = dom_result.scalar_one_or_none()
        domain_id = dom.id if dom is not None else None
        if domain_id is None:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown domain: '{payload.domain}'",
            )
    if domain_id is None:
        raise HTTPException(
            status_code=400,
            detail="No domain specified: pass 'domain_id' or 'domain'",
        )
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
    mappings = []
    for r in rows:
        if r.meta:
            # Rows saved by the current mapping pipeline carry the complete
            # rich dict — return it verbatim (identical to POST /map output).
            mappings.append(dict(r.meta))
        else:
            # Legacy rows (pre-meta): keep the old thin shape.
            mappings.append(
                {
                    "field_id": r.field_id,
                    "field_name": r.field_name,
                    "value": r.value,
                    "confidence": r.confidence,
                    "option_id": r.option_id,
                    "sources": r.sources,
                    "mapping_method": r.mapping_method,
                }
            )
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


@router.get("/{report_id}/documents/{file_id}/file")
async def get_document_file(
    report_id: str,
    file_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stream the stored source file for a report document (source preview).

    Access is gated by the report-user linkage privacy wall: the caller must
    be linked to the report, and the file must belong to that report. Served
    inline so the panel can preview PDFs/images in a popover.
    """
    repo = ReportRepository(db)
    report = await repo.get_report_for_user(report_id, current_user.id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    result = await db.execute(
        select(FileRecord).where(
            FileRecord.id == file_id, FileRecord.report_id == report_id
        )
    )
    file_obj = result.scalar_one_or_none()
    if file_obj is None:
        raise HTTPException(status_code=404, detail="Document not found")

    storage_path = file_obj.storage_path or ""
    path = resolve_transport_path(storage_path) if storage_path else None
    if path is None or not path.is_file():
        # The File row records the nominal upload path, but the physical file
        # is written to the extraction work_dir (uploads/jobs/{job_id}/) and
        # the authoritative path lives on the deduplicated KB Document row
        # (same content hash, same org — privacy wall holds).
        if file_obj.file_hash:
            doc_repo = DocumentRepository(db)
            stored_doc = await doc_repo.get_document_by_hash(
                file_obj.file_hash, org_id=report.organization_id
            )
            if stored_doc and stored_doc.storage_path:
                candidate = resolve_transport_path(stored_doc.storage_path)
                if candidate.is_file():
                    path = candidate
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="File content not available")

    return FileResponse(
        path,
        media_type=file_obj.mime_type or "application/octet-stream",
        filename=file_obj.filename,
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
    x_lock_token: str = Header(default=None),
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

    # Interactive mutation on a shared report -> lock required
    await require_report_lock(report_id, db, current_user.id, x_lock_token)

    # Resolve the knowledge-base document. The report listing surfaces
    # per-report File-row ids, so accept those too and bridge via content hash
    # (org-scoped) to the real document.
    doc = await doc_repo.get_document(document_id)
    if doc is None or doc.deleted_at is not None:
        file_row = (
            await db.execute(
                select(FileRecord).where(
                    FileRecord.id == document_id,
                    FileRecord.report_id == report_id,
                )
            )
        ).scalar_one_or_none()
        if file_row is None or not file_row.file_hash:
            raise HTTPException(status_code=404, detail="Document not found")
        org_id = await resolve_organization(db, current_user)
        doc = await doc_repo.get_document_by_hash(file_row.file_hash, org_id=org_id)
        if doc is None or doc.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Document not found")
        document_id = doc.id

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
