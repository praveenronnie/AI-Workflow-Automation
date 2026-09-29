from datetime import datetime
import uuid

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)

from backend.database.base import Base


class ReportIntent(Base):
    """Persisted per-section form intent (status + stored intent) for a report.

    Source of truth for "are the intents ready?" before mapping proceeds.  Redis
    (``RedisCache.set_intent``) remains the fast cache; this table is the durable
    status store.
    """

    __tablename__ = "report_intents"
    __table_args__ = (
        UniqueConstraint("report_id", "section_id", name="uq_report_intent_section"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id = Column(
        String(36),
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    section_id = Column(String(255), nullable=False)
    section_name = Column(String(255), nullable=True)
    field_count = Column(Integer, default=0)
    intent = Column(JSON, nullable=True)
    status = Column(String(20), default="pending", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
