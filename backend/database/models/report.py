from datetime import datetime
import uuid

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
    Index,
)
from sqlalchemy import text
from sqlalchemy.orm import relationship

from backend.database.base import Base


import enum


class ReportStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    archived = "archived"


class FileStatus(str, enum.Enum):
    uploaded = "uploaded"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class Report(Base):
    __tablename__ = "reports"
    # One report per source_url per organization: a shared report page is a
    # single row regardless of how many users open it. Partial unique index so
    # a soft-deleted row (deleted_at set) does not block re-linking the URL.
    __table_args__ = (
        Index(
            "uq_reports_org_url_active",
            "organization_id",
            "source_url",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id = Column(String(36), index=True)
    status = Column(
        Enum(ReportStatus), default=ReportStatus.pending, nullable=False, index=True
    )
    source_domain = Column(String(100), default="openquire")
    source_url = Column(Text)
    # Soft delete: a report that was "removed" by an admin. Hidden from all
    # queries while set; can be restored on relink (user re-opens the URL).
    deleted_at = Column(DateTime, nullable=True, index=True)
    created_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"))
    meta = Column(JSON, default=dict)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime)
    jobs = relationship("Job", back_populates="report", cascade="all, delete-orphan")

    files = relationship("File", back_populates="report", cascade="all, delete-orphan")

    # Many-to-many: users linked to this report via the ``report_users``
    # junction table. Writes go through ReportUser rows / repository methods;
    # the ``users`` association is read-only convenience.
    report_users = relationship(
        "ReportUser", back_populates="report", cascade="all, delete-orphan"
    )
    users = relationship(
        "User",
        secondary="report_users",
        viewonly=True,
        foreign_keys="[ReportUser.user_id, ReportUser.report_id]",
    )

    # Many-to-many: documents linked to this report (shared knowledge base).
    report_documents = relationship(
        "ReportDocument", back_populates="report", cascade="all, delete-orphan"
    )
    documents = relationship("Document", secondary="report_documents", viewonly=True)


class File(Base):
    __tablename__ = "files"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id = Column(
        String(36),
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    uploaded_by = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    filename = Column(String(255), nullable=False)
    file_size_bytes = Column(Integer)
    mime_type = Column(String(100))
    file_hash = Column(String(64), index=True)
    status = Column(
        Enum(FileStatus), default=FileStatus.uploaded, nullable=False, index=True
    )
    storage_path = Column(Text)
    page_count = Column(Integer)
    meta = Column(JSON, default=dict)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.now())
    updated_at = Column(DateTime, default=datetime.now(), onupdate=datetime.now())
    completed_at = Column(DateTime)

    doc_type = Column(String(50), nullable=True)

    report = relationship("Report", back_populates="files")
