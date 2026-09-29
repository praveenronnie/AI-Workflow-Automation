from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text, JSON

from backend.database.base import Base


class EvidenceBatch(Base):
    __tablename__ = "evidence_batches"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # Nullable: an evidence batch belongs to the DOCUMENT extraction, not to a
    # single report (the same document serves every linked report).
    report_id = Column(
        String(36),
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    status = Column(String(50), default="processing", nullable=False)
    evidence_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)


class Evidence(Base):
    __tablename__ = "evidence"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    batch_id = Column(
        String(36), ForeignKey("evidence_batches.id", ondelete="CASCADE"), index=True
    )
    # Nullable: evidence belongs to the DOCUMENT (shared knowledge base); the
    # report linkage is via document_id → report_documents.
    report_id = Column(
        String(36),
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    # Extraction output belongs to the DOCUMENT (shared knowledge base): when
    # the same document is linked to multiple reports, the evidence rows are
    # created once and referenced by every linked report via document_id.
    document_id = Column(
        String(36), ForeignKey("documents.id", ondelete="SET NULL"), index=True
    )
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_id = Column(
        String(36), ForeignKey("files.id", ondelete="SET NULL"), index=True
    )
    source_type = Column(String(50))
    source_ref = Column(String(255))
    field_name = Column(String(255), index=True)
    value = Column(JSON)
    data_type = Column(String(50), default="string")
    confidence = Column(Float)
    raw_text = Column(Text)
    category = Column(String(255))
    subcategory = Column(String(255))
    tags = Column(JSON, default=list)
    extraction_model = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)


class FormSchema(Base):
    __tablename__ = "form_schemas"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id = Column(
        String(36),
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    schema_json = Column(JSON, nullable=False)
    scanned_payload = Column(JSON, nullable=True)
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MappingResult(Base):
    __tablename__ = "mapping_results"

    id = Column(Integer, primary_key=True)
    report_id = Column(
        String(36),
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    field_name = Column(String(255))
    field_id = Column(String(255))
    value = Column(JSON)
    confidence = Column(Float)
    option_id = Column(String(255))
    sources = Column(JSON, default=list)
    mapping_method = Column(String(50))
    # Full rich mapping dict (section_name, table_id, matched, reasoning,
    # source, source_location, source_ref, source_excerpt, ...) so the
    # read-back endpoint can return the exact same shape as POST /map.
    meta = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
