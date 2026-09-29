import asyncio
import logging
from datetime import datetime
import uuid

from sqlalchemy import select, func, update, delete, or_, and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from backend.database.models.report import Report, File, ReportStatus, FileStatus
from backend.database.models.documents import ReportDocument, ReportUser
from backend.database.models.job import Job
from backend.database.models.evidence import (
    Evidence,
    EvidenceBatch,
    MappingResult,
    FormSchema,
)
from backend.database.models.domain import Domain
from backend.database.models.user import User
from backend.database.models.intent import ReportIntent
from typing import Optional, List


def normalize_url(url: str) -> str:
    """Canonical form for report dedup: lowercase scheme/host, no fragment,
    no default port, no trailing slash, order-insensitive query params.

    Non-http(s) or unparseable input returns the stripped original so callers
    can fall back to a URL-less report instead of crashing.
    """
    url = (url or "").strip()
    if not url:
        return ""
    try:
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            return url
        host = (parts.hostname or "").lower()
        port = parts.port
        default = {"http": 80, "https": 443}.get(parts.scheme)
        netloc = host if port in (None, default) else f"{host}:{port}"
        path = parts.path.rstrip("/") or "/"
        query = urlencode(sorted(parse_qsl(parts.query, keep_blank_values=True)))
        return urlunsplit((parts.scheme.lower(), netloc, path, query, ""))
    except ValueError:
        return url

logger = logging.getLogger(__name__)


class ReportRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.lock = asyncio.Lock()

    async def ensure_user_linked(self, report_id: str, user_id: str) -> bool:
        """Ensure the user is linked to the report via ``report_users`` (idempotent)."""
        result = await self.session.execute(
            select(ReportUser).where(
                ReportUser.report_id == report_id, ReportUser.user_id == user_id
            )
        )
        link = result.scalar_one_or_none()
        if link is not None:
            return False
        self.session.add(
            ReportUser(report_id=report_id, user_id=user_id, linked_by=user_id)
        )
        await self.session.commit()
        return True

    async def get_or_create_report_by_url(
        self,
        organization_id: str,
        source_url: str,
        user_id: str,
        source_domain: str = "openquire",
    ) -> tuple:
        """Resolve the single shared report for a URL and link the user to it.

        One report per URL per organization (enforced by a partial unique index
        on ``(organization_id, source_url)``). Returns
        ``(report, created, restored, linked)``; the user is ALWAYS linked to
        the resulting report so follow-up calls (map/upload/mapping) work.
        """
        report = await self.find_report_by_url(
            organization_id, normalize_url(source_url)
        )
        created = False
        restored = False
        if report is None:
            # A soft-deleted row can be restored instead of creating a new one.
            report = await self.find_report_by_url(
                organization_id, normalize_url(source_url), include_deleted=True
            )
            if report is not None:
                await self.restore_report(report.id)
                restored = True
                await self.session.refresh(report)
        if report is None:
            try:
                report = await self.create_report(
                    user_id,
                    organization_id,
                    source_url=normalize_url(source_url),
                    source_domain=source_domain,
                    commit=False,
                )
                created = True
            except IntegrityError:
                # Race: another concurrent request created the same (org, url)
                # report between our check and our insert. Roll back the torn
                # session and link the winner's report instead of 500-ing.
                await self.session.rollback()
                report = await self.find_report_by_url(
                    organization_id, normalize_url(source_url)
                )
                if report is None:
                    report = await self.find_report_by_url(
                        organization_id,
                        normalize_url(source_url),
                        include_deleted=True,
                    )
                if report is None:
                    raise
                await self.restore_report(report.id)
                await self.session.refresh(report)
        linked = await self.ensure_user_linked(report.id, user_id)
        # Single commit covering create (when ours) + the user link, so a
        # crash in between cannot orphan a report from its creator.
        await self.session.commit()
        return report, created, restored, linked

    async def create_report(
        self,
        user_id: str,
        organization_id: str,
        source_url: str = None,
        source_domain: str = "openquire",
        commit: bool = True,
    ) -> Report:
        async with self.lock:
            report = Report(
                organization_id=organization_id,
                session_id=str(uuid.uuid4()),
                status=ReportStatus.pending,
                source_url=source_url,
                source_domain=source_domain,
                created_by=user_id,
            )
            self.session.add(report)
            if commit:
                await self.session.commit()
            else:
                # Assign the id and make the instance persistent without
                # ending the caller's transaction.
                await self.session.flush()
            await self.session.refresh(report)
            return report

    async def get_report(self, report_id: str, include_deleted: bool = False) -> Report:
        """Fetch a report. Soft-deleted reports are hidden by default."""
        report = await self.session.get(Report, report_id)
        if report is None:
            return None
        if not include_deleted and report.deleted_at is not None:
            return None
        return report

    async def get_report_for_user(self, report_id: str, user_id: str) -> Report:
        """Fetch a report the user is *linked to* (report_users membership).

        Replaces the old single-owner ``Report.user_id`` check — reports are
        shared across users in the knowledge-base model.
        """
        report = await self.get_report(report_id)
        if report is None:
            return None
        result = await self.session.execute(
            select(ReportUser.id).where(
                ReportUser.report_id == report_id, ReportUser.user_id == user_id
            )
        )
        if result.scalar_one_or_none() is None:
            return None
        return report

    async def get_reports_by_user(self, user_id: str) -> List[Report]:
        """All non-deleted reports the user is linked to."""
        result = await self.session.execute(
            select(Report)
            .join(ReportUser, ReportUser.report_id == Report.id)
            .where(ReportUser.user_id == user_id, Report.deleted_at.is_(None))
            .order_by(Report.created_at.desc())
        )
        return result.scalars().all()

    async def find_report_by_url(
        self,
        organization_id: str,
        source_url: str,
        include_deleted: bool = False,
    ) -> Optional[Report]:
        """Find a report by its source URL within an organization.

        Reports are deduplicated by URL: the same OpenQuire report page maps
        to ONE shared report regardless of how many users open it.
        """
        stmt = select(Report).where(
            Report.organization_id == organization_id,
            Report.source_url == source_url,
        )
        if not include_deleted:
            stmt = stmt.where(Report.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def soft_delete_report(self, report_id: str) -> bool:
        report = await self.session.get(Report, report_id)
        if not report or report.deleted_at is not None:
            return False
        report.deleted_at = datetime.utcnow()
        await self.session.commit()
        return True

    async def restore_report(self, report_id: str) -> bool:
        report = await self.session.get(Report, report_id)
        if not report:
            return False
        report.deleted_at = None
        await self.session.commit()
        return True

    async def purge_report(self, report_id: str) -> bool:
        """Physically delete a report row. Associations cascade via FK
        ondelete=CASCADE (report_users, report_documents, form_schemas,
        mapping_results, jobs, evidence_batches, intents). Evidence rows and
        Qdrant points referencing the report are cleaned by the caller
        (admin endpoint) before/after invoking this."""
        report = await self.session.get(Report, report_id)
        if not report:
            return False
        await self.session.delete(report)
        await self.session.commit()
        return True

    async def get_domain_by_id(self, domain_id: int) -> Optional[Domain]:
        """Fetch a domain by its integer primary key."""
        try:
            result = await self.session.execute(
                select(Domain).where(Domain.id == domain_id)
            )
            domain = result.scalar_one_or_none()
            if domain is None:
                logger.warning(
                    "[DB] get_domain_by_id: domain_id=%s not found", domain_id
                )
            return domain
        except Exception as exc:
            logger.error(
                "[DB] get_domain_by_id failed: domain_id=%s error=%s",
                domain_id,
                exc,
                exc_info=True,
            )
            return None

    async def get_default_domain(self) -> Optional[Domain]:
        """Fetch the first active domain (lowest id) as the system default.

        Used by flows (e.g. the intent pre-pass) that run before the client
        has supplied an explicit ``domain_id``.
        """
        try:
            result = await self.session.execute(
                select(Domain)
                .where(Domain.is_active == 1)
                .order_by(Domain.id.asc())
                .limit(1)
            )
            domain = result.scalar_one_or_none()
            if domain is None:
                logger.warning("[DB] get_default_domain: no active domains found")
            return domain
        except Exception as exc:
            logger.error("[DB] get_default_domain failed: %s", exc, exc_info=True)
            return None

    async def get_form_schema_for_report(self, report_id: str) -> Optional[FormSchema]:
        result = await self.session.execute(
            select(FormSchema)
            .where(FormSchema.report_id == report_id)
            .order_by(FormSchema.version.desc())
        )
        return result.scalar_one_or_none()

    async def set_report_status(
        self, report_id: str, status: ReportStatus, error: str = None
    ):
        async with self.lock:
            values = {"status": status, "updated_at": datetime.utcnow()}
            if status == ReportStatus.completed:
                values["completed_at"] = datetime.utcnow()
            if error:
                values["error_message"] = error
            await self.session.execute(
                update(Report).where(Report.id == report_id).values(**values)
            )
            await self.session.commit()

    async def create_file(
        self,
        report_id: str,
        filename: str,
        mime_type: str = None,
        file_hash: str = None,
        file_size: int = None,
        storage_path: str = None,
        uploaded_by: str = None,
        doc_type: str = None,
    ) -> File:
        async with self.lock:
            file = File(
                report_id=report_id,
                filename=filename,
                mime_type=mime_type,
                file_hash=file_hash,
                file_size_bytes=file_size,
                storage_path=storage_path,
                uploaded_by=uploaded_by,
                status=FileStatus.uploaded,
                doc_type=doc_type,
            )
            self.session.add(file)
            await self.session.commit()
            await self.session.refresh(file)
            logger.info(
                "DB: file record created: file_id=%s report_id=%s filename=%s",
                file.id,
                file.report_id,
                file.filename,
            )
            return file

    async def set_file_status(
        self, file_id: str, status: FileStatus, error: str = None
    ):
        async with self.lock:
            values = {"status": status, "updated_at": datetime.utcnow()}
            if status == FileStatus.completed:
                values["completed_at"] = datetime.utcnow()
            if error:
                values["error_message"] = error
            await self.session.execute(
                update(File).where(File.id == file_id).values(**values)
            )
            await self.session.commit()

    async def get_files(self, report_id: str):
        result = await self.session.execute(
            select(File).where(File.report_id == report_id).order_by(File.created_at)
        )
        return result.scalars().all()

    async def update_file_metadata(
        self, file_id: str, page_count: int = None, meta: dict = None
    ):
        async with self.lock:
            values = {}
            if page_count is not None:
                values["page_count"] = page_count
            if meta:
                values["meta"] = meta
            if values:
                values["updated_at"] = datetime.utcnow()
                await self.session.execute(
                    update(File).where(File.id == file_id).values(**values)
                )
                await self.session.commit()

    async def create_batch(self, report_id: str) -> EvidenceBatch:
        async with self.lock:
            batch = EvidenceBatch(report_id=report_id, status="processing")
            self.session.add(batch)
            await self.session.commit()
            await self.session.refresh(batch)
            return batch

    async def complete_batch(self, batch_id: str, evidence_count: int):
        async with self.lock:
            await self.session.execute(
                update(EvidenceBatch)
                .where(EvidenceBatch.id == batch_id)
                .values(
                    status="completed",
                    evidence_count=evidence_count,
                    completed_at=datetime.utcnow(),
                )
            )
            await self.session.commit()
            logger.info(
                "DB: batch completed: batch_id=%s evidence_count=%d",
                batch_id,
                evidence_count,
            )

    async def add_evidence(
        self,
        batch_id: str,
        report_id: str,
        file_id: str,
        evidence_list: list,
        user_id: str = None,
    ):
        async with self.lock:
            for ev in evidence_list:
                uid = user_id or getattr(ev, "user_id", None)
                self.session.add(
                    Evidence(
                        batch_id=batch_id,
                        report_id=report_id,
                        user_id=uid,
                        file_id=file_id,
                        source_type=ev.source_type,
                        source_ref=ev.source_ref,
                        field_name=ev.field_name,
                        value=ev.value,
                        data_type=ev.data_type,
                        confidence=ev.confidence,
                        raw_text=ev.raw_text,
                        category=ev.category,
                        subcategory=ev.subcategory,
                        tags=ev.tags or [],
                        extraction_model=ev.extraction_model,
                    )
                )
            await self.session.commit()
            logger.info(
                "DB: evidence committed: batch_id=%s report_id=%s file_id=%s count=%d",
                batch_id,
                report_id,
                file_id,
                len(evidence_list),
            )

    async def get_evidence(self, report_id: str):
        """All evidence accessible to a report: evidence of documents currently
        linked to it (shared knowledge base) plus legacy report-scoped rows."""
        result = await self.session.execute(
            select(Evidence)
            .outerjoin(
                ReportDocument, ReportDocument.document_id == Evidence.document_id
            )
            .where(
                or_(
                    ReportDocument.report_id == report_id,
                    and_(
                        Evidence.report_id == report_id,
                        Evidence.document_id.is_(None),
                    ),
                )
            )
            .order_by(Evidence.created_at)
        )
        return result.scalars().all()

    async def save_form_schema(
        self, report_id: str, schema_json: dict, scanned_payload: dict = None
    ):
        async with self.lock:
            latest = await self.get_form_schema_for_report(report_id)
            if latest is not None:
                latest.schema_json = schema_json
                if scanned_payload is not None:
                    latest.scanned_payload = scanned_payload
                latest.version = (latest.version or 1) + 1
                latest.updated_at = datetime.utcnow()
                await self.session.commit()
                logger.info("DB: form schema upserted: report_id=%s", report_id)
                return latest
            schema = FormSchema(
                report_id=report_id,
                schema_json=schema_json,
                scanned_payload=scanned_payload,
                version=1,
            )
            self.session.add(schema)
            await self.session.commit()
            logger.info("DB: form schema saved: report_id=%s", report_id)
            return schema

    async def save_mapping_results(self, report_id: str, results: list):
        async with self.lock:
            # Replace prior rows so readback always returns one consistent set.
            await self.session.execute(
                delete(MappingResult).where(MappingResult.report_id == report_id)
            )
            for r in results:
                self.session.add(
                    MappingResult(
                        report_id=report_id,
                        field_name=r.get("field_name"),
                        field_id=r.get("field_id"),
                        value=r.get("value"),
                        confidence=r.get("confidence"),
                        option_id=r.get("option_id"),
                        sources=r.get("sources", []),
                        mapping_method=r.get("mapping_method"),
                        # Persist the complete rich mapping so the read-back
                        # endpoint returns the exact POST /map shape.
                        meta=dict(r),
                    )
                )
            await self.session.commit()
            logger.info(
                "DB: mapping results saved: report_id=%s rows=%d",
                report_id,
                len(results),
            )

    async def get_report_count(self) -> int:
        return await self.session.execute(select(func.count(Report.id)))

    async def get_file_by_hash(self, report_id: str, file_hash: str) -> Optional[File]:
        """Return an existing File for a report with the same content hash, if any."""
        result = await self.session.execute(
            select(File).where(File.report_id == report_id, File.file_hash == file_hash)
        )
        return result.scalars().first()

    async def update_file_extraction_state(
        self, file_id: str, extraction_status: str, error: str = None
    ):
        """Persist per-file extraction status in File.meta (embedding status excluded)."""
        file = await self.session.get(File, file_id)
        if file is None:
            return
        meta = dict(file.meta or {})
        meta["extraction_status"] = extraction_status
        if error:
            meta["error"] = error
        file.meta = meta
        if extraction_status == "processing":
            file.status = FileStatus.processing
        elif extraction_status == "completed":
            file.status = FileStatus.completed
            file.completed_at = datetime.utcnow()
        elif extraction_status == "failed":
            file.status = FileStatus.failed
            file.error_message = error
        await self.session.commit()
        logger.info(
            "DB: file extraction state=%s file_id=%s report_id=%s filename=%s",
            extraction_status,
            file_id,
            file.report_id,
            file.filename,
        )

    async def are_all_files_completed(self, report_id: str) -> bool:
        """True when every file attached to the report reached completed status."""
        result = await self.session.execute(
            select(File.status).where(File.report_id == report_id)
        )
        statuses = result.scalars().all()
        if not statuses:
            return False
        return all(s == FileStatus.completed.value for s in statuses)

    async def get_report_processing_status(self, report_id: str) -> dict:
        """Aggregate per-report processing status (docs, filenames, mapping, intents)."""
        files = await self.get_files(report_id)
        filenames = [f.filename for f in files]
        extraction_completed = (
            all(f.status == FileStatus.completed for f in files) if files else False
        )
        result = await self.session.execute(
            select(Job)
            .where(
                Job.report_id == report_id,
                Job.job_type == "map",
                Job.status == "completed",
            )
            .limit(1)
        )
        mapping_done = result.scalar_one_or_none() is not None
        intent_total = (
            await self.session.execute(
                select(func.count(ReportIntent.id)).where(
                    ReportIntent.report_id == report_id
                )
            )
        ).scalar()
        intent_done = (
            await self.session.execute(
                select(func.count(ReportIntent.id)).where(
                    ReportIntent.report_id == report_id,
                    ReportIntent.status == "completed",
                )
            )
        ).scalar()
        if intent_total and intent_done == intent_total:
            intent_status = "completed"
        else:
            intent_status = "pending" if not intent_total else "processing"
        return {
            "report_id": report_id,
            "total_documents": len(files),
            "filenames": filenames,
            "extraction_completed": extraction_completed,
            "mapping_done": mapping_done,
            "intent_status": intent_status,
        }

    async def save_section_intent(
        self,
        report_id: str,
        section_id: str,
        section_name: str,
        field_count: int,
        intent: dict,
    ):
        async with self.lock:
            result = await self.session.execute(
                select(ReportIntent).where(
                    ReportIntent.report_id == report_id,
                    ReportIntent.section_id == section_id,
                )
            )
            row = result.scalar_one_or_none()
            if row is None:
                row = ReportIntent(report_id=report_id, section_id=section_id)
                self.session.add(row)
            row.section_name = section_name
            row.field_count = field_count
            row.intent = intent
            row.status = "completed"
            row.updated_at = datetime.utcnow()
            await self.session.commit()
            return row

    async def are_intents_ready(self, report_id: str, section_count: int) -> bool:
        result = await self.session.execute(
            select(func.count(ReportIntent.id)).where(
                ReportIntent.report_id == report_id,
                ReportIntent.status == "completed",
            )
        )
        return result.scalar() >= section_count

    async def get_intents(self, report_id: str) -> dict:
        result = await self.session.execute(
            select(ReportIntent).where(ReportIntent.report_id == report_id)
        )
        rows = result.scalars().all()
        return {
            r.section_id: {
                "section_name": r.section_name,
                "field_count": r.field_count,
                "intent": r.intent,
                "status": r.status,
            }
            for r in rows
        }

    async def get_user_email(self, user_id: str) -> str:
        user = await self.session.get(User, user_id)
        return user.email if user else ""

    async def create_job(self, report_id: str, user_id: str, job_type: str) -> Job:
        job = Job(
            id=str(uuid.uuid4()),
            report_id=report_id,
            user_id=user_id,
            job_type=job_type,
            status="queued",
        )
        self.session.add(job)
        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def get_job(self, job_id: str) -> Job | None:
        return await self.session.get(Job, job_id)

    async def delete_file_by_report_and_hash(
        self, report_id: str, content_hash: str
    ) -> int:
        """Remove the per-report File row(s) matching a document's content hash.

        Keeps ``reports.files`` (report read-back) in sync with the
        ``report_documents`` link — a document unlinked from a report must no
        longer appear in that report's file list.
        """
        result = await self.session.execute(
            delete(File).where(
                File.report_id == report_id, File.file_hash == content_hash
            )
        )
        await self.session.commit()
        return result.rowcount

    async def bulk_insert_evidence(self, evidence_list: list) -> list:
        if not evidence_list:
            return []

        async with self.lock:
            rows = []
            for ev in evidence_list:
                rows.append(
                    Evidence(
                        batch_id=getattr(ev, "evidence_batch_id", None)
                        or getattr(ev, "batch_id", None),
                        report_id=getattr(ev, "report_id", None),
                        user_id=getattr(ev, "user_id", None),
                        file_id=getattr(ev, "file_id", None),
                        document_id=getattr(ev, "document_id", None),
                        source_type=getattr(ev, "source_type", None),
                        source_ref=getattr(ev, "source_ref", None),
                        field_name=getattr(ev, "field_name", None),
                        value=getattr(ev, "value", None),
                        data_type=getattr(ev, "data_type", None) or "string",
                        confidence=getattr(ev, "confidence", None),
                        raw_text=getattr(ev, "raw_text", None),
                        category=getattr(ev, "category", None),
                        subcategory=getattr(ev, "subcategory", None),
                        tags=getattr(ev, "tags", None) or [],
                        extraction_model=getattr(ev, "extraction_model", None),
                    )
                )
            self.session.add_all(rows)
            await self.session.commit()
            logger.info("DB: bulk-inserted evidence: count=%d", len(rows))
            return [r.id for r in rows]

    async def update_job_status(
        self, job_id: str, status: str, error: str | None = None
    ):
        job = await self.session.get(Job, job_id)
        if not job:
            return
        job.status = status
        if error:
            job.error = error
        if status == "processing" and not job.started_at:
            job.started_at = datetime.now()
        if status == "completed":
            job.completed_at = datetime.now()
        await self.session.commit()
        return None
