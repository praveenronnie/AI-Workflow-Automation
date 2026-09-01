"""Repository for the shared knowledge base: documents, report links,
report locks, and share links.

Deletion semantics (see models/documents.py):
- documents / reports  -> soft delete (deleted_at)
- link rows            -> hard delete on unlink (pure associations)
- physical purge       -> explicit admin-only repository methods
"""

import logging
import secrets
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from inspection_ai.database.models.documents import (
    Document,
    ReportDocument,
    ReportLock,
    ReportUser,
    ShareLink,
)
from inspection_ai.database.models.evidence import Evidence
from inspection_ai.core.config import get_settings

logger = logging.getLogger(__name__)


class DocumentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ------------------------------------------------------------------ #
    # Documents
    # ------------------------------------------------------------------ #

    async def get_document(self, document_id: str) -> Optional[Document]:
        return await self.session.get(Document, document_id)

    async def get_document_by_hash(
        self, content_hash: str, include_deleted: bool = False
    ) -> Optional[Document]:
        """Find an active (non-deleted) document by content hash."""
        stmt = select(Document).where(Document.content_hash == content_hash)
        if not include_deleted:
            stmt = stmt.where(Document.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_document(
        self,
        *,
        content_hash: str,
        filename: str,
        mime_type: str = None,
        file_size: int = None,
        doc_type: str = "scanned",
        storage_path: str = None,
        created_by: str = None,
    ) -> Document:
        doc = Document(
            content_hash=content_hash,
            filename=filename,
            mime_type=mime_type,
            file_size_bytes=file_size,
            doc_type=doc_type,
            storage_path=storage_path,
            extraction_status="pending",
            created_by=created_by,
        )
        self.session.add(doc)
        await self.session.commit()
        await self.session.refresh(doc)
        return doc

    async def update_extraction_state(
        self, document_id: str, status: str, error: str = None
    ) -> None:
        doc = await self.session.get(Document, document_id)
        if not doc:
            return
        doc.extraction_status = status
        if status == "completed":
            doc.extracted_at = datetime.utcnow()
        await self.session.commit()

    async def soft_delete_document(self, document_id: str) -> bool:
        doc = await self.session.get(Document, document_id)
        if not doc or doc.deleted_at is not None:
            return False
        doc.deleted_at = datetime.utcnow()
        await self.session.commit()
        return True

    async def restore_document(self, document_id: str) -> bool:
        doc = await self.session.get(Document, document_id)
        if not doc:
            return False
        doc.deleted_at = None
        await self.session.commit()
        return True

    # ------------------------------------------------------------------ #
    # Document <-> Report links
    # ------------------------------------------------------------------ #

    async def link_document_report(
        self, document_id: str, report_id: str, user_id: str
    ) -> Tuple[ReportDocument, bool]:
        """Link a document to a report. Returns (link, created).

        Idempotent: re-linking returns the existing row with created=False.
        """
        result = await self.session.execute(
            select(ReportDocument).where(
                ReportDocument.document_id == document_id,
                ReportDocument.report_id == report_id,
            )
        )
        link = result.scalar_one_or_none()
        if link is not None:
            return link, False
        link = ReportDocument(
            document_id=document_id,
            report_id=report_id,
            linked_by=user_id,
        )
        self.session.add(link)
        await self.session.commit()
        await self.session.refresh(link)
        return link, True

    async def unlink_document_report(self, document_id: str, report_id: str) -> bool:
        result = await self.session.execute(
            delete(ReportDocument).where(
                ReportDocument.document_id == document_id,
                ReportDocument.report_id == report_id,
            )
        )
        await self.session.commit()
        return result.rowcount > 0

    async def get_document_report_ids(self, document_id: str) -> List[str]:
        result = await self.session.execute(
            select(ReportDocument.report_id).where(
                ReportDocument.document_id == document_id
            )
        )
        return [r for (r,) in result.all()]

    async def get_document_ids_for_report(self, report_id: str) -> List[str]:
        result = await self.session.execute(
            select(ReportDocument.document_id).where(
                ReportDocument.report_id == report_id
            )
        )
        return [d for (d,) in result.all()]

    async def get_documents_for_report(self, report_id: str) -> List[Document]:
        result = await self.session.execute(
            select(Document)
            .join(ReportDocument, ReportDocument.document_id == Document.id)
            .where(
                ReportDocument.report_id == report_id,
                Document.deleted_at.is_(None),
            )
            .order_by(ReportDocument.linked_at.desc())
        )
        return result.scalars().all()

    async def get_document_stats(self, document_id: str) -> dict:
        """'Uploaded by these many users' + link count for a document."""
        result = await self.session.execute(
            select(
                func.count(ReportDocument.id),
                func.count(func.distinct(ReportDocument.linked_by)),
            ).where(ReportDocument.document_id == document_id)
        )
        total_links, distinct_users = result.one()
        return {
            "report_links": total_links or 0,
            "distinct_uploaders": distinct_users or 0,
        }

    async def get_evidence_by_document(self, document_id: str) -> List[Evidence]:
        result = await self.session.execute(
            select(Evidence).where(Evidence.document_id == document_id)
        )
        return result.scalars().all()

    # ------------------------------------------------------------------ #
    # Report <-> User links
    # ------------------------------------------------------------------ #

    async def link_user_report(
        self, report_id: str, user_id: str, linked_by: str = None
    ) -> Tuple[ReportUser, bool]:
        result = await self.session.execute(
            select(ReportUser).where(
                ReportUser.report_id == report_id,
                ReportUser.user_id == user_id,
            )
        )
        link = result.scalar_one_or_none()
        if link is not None:
            return link, False
        link = ReportUser(
            report_id=report_id,
            user_id=user_id,
            linked_by=linked_by or user_id,
        )
        self.session.add(link)
        await self.session.commit()
        await self.session.refresh(link)
        return link, True

    async def unlink_user_report(self, report_id: str, user_id: str) -> bool:
        result = await self.session.execute(
            delete(ReportUser).where(
                ReportUser.report_id == report_id,
                ReportUser.user_id == user_id,
            )
        )
        await self.session.commit()
        return result.rowcount > 0

    async def is_user_linked(self, report_id: str, user_id: str) -> bool:
        result = await self.session.execute(
            select(ReportUser.id).where(
                ReportUser.report_id == report_id,
                ReportUser.user_id == user_id,
            )
        )
        return result.scalar_one_or_none() is not None

    # ------------------------------------------------------------------ #
    # Report locks
    # ------------------------------------------------------------------ #

    async def get_lock(self, report_id: str) -> Optional[ReportLock]:
        return await self.session.get(ReportLock, report_id)

    async def acquire_lock(
        self, report_id: str, user_id: str, ttl_seconds: int = None
    ) -> dict:
        """Try to acquire (or renew) the report lock.

        Returns ``{"status": "acquired"|"held", ...}``. ``acquired`` covers:
        no lock, stale (expired) lock, or re-acquire by the same user.
        """
        ttl = ttl_seconds or get_settings().report_lock_ttl_seconds
        now = datetime.utcnow()
        expires = now + timedelta(seconds=ttl)

        lock = await self.get_lock(report_id)
        if lock is not None:
            fresh = lock.expires_at is not None and lock.expires_at > now
            if fresh and lock.locked_by != user_id:
                return {
                    "status": "held",
                    "locked_by": lock.locked_by,
                    "expires_at": lock.expires_at.isoformat(),
                }
            # Stale, expired, or same user -> (re)acquire
            lock.locked_by = user_id
            lock.lock_token = secrets.token_hex(32)
            lock.acquired_at = now
            lock.last_heartbeat_at = now
            lock.expires_at = expires
            lock.mapping_in_progress = 0
            await self.session.commit()
            return {
                "status": "acquired",
                "lock_token": lock.lock_token,
                "expires_at": expires.isoformat(),
            }

        lock = ReportLock(
            report_id=report_id,
            locked_by=user_id,
            lock_token=secrets.token_hex(32),
            expires_at=expires,
        )
        self.session.add(lock)
        try:
            await self.session.commit()
        except Exception:
            # Lost an insert race -> someone else holds it
            await self.session.rollback()
            lock = await self.get_lock(report_id)
            return {
                "status": "held",
                "locked_by": lock.locked_by if lock else None,
                "expires_at": lock.expires_at.isoformat() if lock else None,
            }
        return {
            "status": "acquired",
            "lock_token": lock.lock_token,
            "expires_at": expires.isoformat(),
        }

    async def heartbeat_lock(
        self, report_id: str, user_id: str, lock_token: str, ttl_seconds: int = None
    ) -> bool:
        lock = await self.get_lock(report_id)
        if (
            lock is None
            or lock.locked_by != user_id
            or lock.lock_token != lock_token
        ):
            return False
        ttl = ttl_seconds or get_settings().report_lock_ttl_seconds
        lock.last_heartbeat_at = datetime.utcnow()
        lock.expires_at = datetime.utcnow() + timedelta(seconds=ttl)
        await self.session.commit()
        return True

    async def release_lock(self, report_id: str, user_id: str, lock_token: str) -> bool:
        lock = await self.get_lock(report_id)
        if lock is None or lock.locked_by != user_id or lock.lock_token != lock_token:
            return False
        await self.session.delete(lock)
        await self.session.commit()
        return True

    async def force_release_lock(self, report_id: str) -> bool:
        lock = await self.get_lock(report_id)
        if lock is None:
            return False
        await self.session.delete(lock)
        await self.session.commit()
        return True

    async def set_mapping_in_progress(self, report_id: str, in_progress: bool) -> bool:
        """Keep the lock alive while a server-side mapping run executes so it
        cannot expire (and be taken over) mid-map."""
        lock = await self.get_lock(report_id)
        if lock is None:
            return False
        lock.mapping_in_progress = 1 if in_progress else 0
        if in_progress:
            lock.expires_at = datetime.utcnow() + timedelta(
                seconds=get_settings().report_lock_ttl_seconds
            )
        await self.session.commit()
        return True

    # ------------------------------------------------------------------ #
    # Share links
    # ------------------------------------------------------------------ #

    async def create_share_link(
        self,
        report_id: str,
        created_by: str,
        expires_days: int = 30,
    ) -> ShareLink:
        link = ShareLink(
            report_id=report_id,
            token=secrets.token_urlsafe(32),
            created_by=created_by,
            expires_at=(
                datetime.utcnow() + timedelta(days=expires_days)
                if expires_days
                else None
            ),
        )
        self.session.add(link)
        await self.session.commit()
        await self.session.refresh(link)
        return link

    async def revoke_share_link(self, token: str) -> bool:
        result = await self.session.execute(
            select(ShareLink).where(ShareLink.token == token)
        )
        link = result.scalar_one_or_none()
        if link is None or link.revoked_at is not None:
            return False
        link.revoked_at = datetime.utcnow()
        await self.session.commit()
        return True

    async def get_valid_share_link(self, token: str) -> Optional[ShareLink]:
        """Return the share link only if valid (exists, not revoked, not expired)."""
        result = await self.session.execute(
            select(ShareLink).where(ShareLink.token == token)
        )
        link = result.scalar_one_or_none()
        if link is None or link.revoked_at is not None:
            return None
        if link.expires_at is not None and link.expires_at < datetime.utcnow():
            return None
        return link
