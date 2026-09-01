"""Shared knowledge-base models.

Everything is *linked*, not duplicated:

- ``documents``        : global, deduplicated by content hash. Extraction output
                         (evidence) belongs to the document, not to a report.
- ``report_documents`` : links documents to reports ("documents.report_ids").
- ``report_users``     : links users to reports ("reports.user_ids").
- ``report_locks``     : advisory locks so only one user processes a report
                         interactively at a time.
- ``share_links``      : tokenized read-only share URLs for mapping results.

Deletion semantics:
- Rows in ``documents`` / ``reports`` are SOFT deleted (``deleted_at``).
- Link rows (report_documents / report_users) are hard-deleted on unlink —
  they are pure associations, restoring access = re-linking.
- Physical purge is an explicit admin action.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from inspection_ai.database.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Document(Base):
    """A unique uploaded document, deduplicated globally by content hash."""

    __tablename__ = "documents"
    __table_args__ = (
        # Same content may be re-uploaded after a soft delete → partial index.
        Index(
            "uq_documents_content_hash_active",
            "content_hash",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    content_hash = Column(String(64), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    mime_type = Column(String(100))
    file_size_bytes = Column(Integer)
    doc_type = Column(String(50), default="scanned")  # scanned | handwritten | image
    storage_path = Column(Text)
    extraction_status = Column(String(50), default="pending", index=True)
    extracted_at = Column(DateTime)
    extraction_model = Column(String(100))
    created_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime, default=datetime.now())
    deleted_at = Column(DateTime, nullable=True, index=True)

    # Reports this document is linked to (shared knowledge base — read-only
    # convenience; writes go through ReportDocument rows).
    report_documents = relationship(
        "ReportDocument", back_populates="document", cascade="all, delete-orphan"
    )
    reports = relationship("Report", secondary="report_documents", viewonly=True)


class ReportDocument(Base):
    """Link: a document is related to a report (many-to-many)."""

    __tablename__ = "report_documents"
    __table_args__ = (
        UniqueConstraint("document_id", "report_id", name="uq_doc_report"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    document_id = Column(
        String(36),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    report_id = Column(
        String(36),
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    linked_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"))
    linked_at = Column(DateTime, default=datetime.now())

    document = relationship("Document", back_populates="report_documents")
    report = relationship("Report", back_populates="report_documents")


class ReportUser(Base):
    """Link: a user has access to a report (many-to-many)."""

    __tablename__ = "report_users"
    __table_args__ = (UniqueConstraint("report_id", "user_id", name="uq_report_user"),)

    id = Column(String(36), primary_key=True, default=_uuid)
    report_id = Column(
        String(36),
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    linked_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"))
    linked_at = Column(DateTime, default=datetime.now())

    report = relationship(
        "Report",
        back_populates="report_users",
        foreign_keys=[report_id],
    )
    user = relationship(
        "User",
        back_populates="report_links",
        foreign_keys=[user_id],
    )


class ReportLock(Base):
    """Advisory lock: only one user processes a report interactively at a time.

    Locks auto-expire — a lock whose ``expires_at`` is in the past is stale and
    may be taken over. The extension heartbeats to renew while active.
    """

    __tablename__ = "report_locks"

    report_id = Column(
        String(36),
        ForeignKey("reports.id", ondelete="CASCADE"),
        primary_key=True,
    )
    locked_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"))
    lock_token = Column(String(64), nullable=False)
    acquired_at = Column(DateTime, default=datetime.now())
    last_heartbeat_at = Column(DateTime, default=datetime.now())
    expires_at = Column(DateTime, nullable=False)
    # Set while an async mapping job is running server-side so the lock is not
    # considered stale mid-map even if the client stops heartbeating.
    mapping_in_progress = Column(Integer, default=0)


class ShareLink(Base):
    """Tokenized read-only share URL for a report's mapping results."""

    __tablename__ = "share_links"

    id = Column(String(36), primary_key=True, default=_uuid)
    report_id = Column(
        String(36),
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token = Column(String(64), unique=True, nullable=False, index=True)
    created_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"))
    expires_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
