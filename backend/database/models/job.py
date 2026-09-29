from datetime import datetime
import uuid

from sqlalchemy import Column, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship

from backend.database.base import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id = Column(
        String(36),
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(String(36), nullable=False, index=True)
    job_type = Column(String(20), nullable=False)  # "pdf" or "image_batch"
    status = Column(String(20), default="queued", nullable=False, index=True)
    payload = Column(Text, nullable=True)  # optional extra data (file names etc.)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error = Column(Text, nullable=True)

    # Relationships
    report = relationship("Report", back_populates="jobs")
