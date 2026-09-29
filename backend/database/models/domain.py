"""Domain & Prompt master-data tables.

These tables provide the *configuration* the front‑end uses to discover
which domain it is operating on and which intent prompts belong to it.

The domain table is intentionally platform‑agnostic: a row represents a
“domain type” (e.g. `site_inspection`, `invoice_processing`, `pca`, …).
The prompt table holds the human written instructions (often LLM prompts)
that the backend uses when normalising or classifying data for that domain.

New endpoints for these tables live in ``backend/features/domains/routes.py``
and do **not** modify the reports feature.
"""

from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from backend.database.base import Base


class Domain(Base):
    __tablename__ = "domains"
    __table_args__ = (UniqueConstraint("name", name="uq_domain_name"),)

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    display_name = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    version = Column(String(50), nullable=False, default="1.0.0")
    is_active = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.now())
    updated_at = Column(DateTime, default=datetime.now(), onupdate=datetime.now())

    prompts = relationship(
        "Prompt", back_populates="domain", cascade="all, delete-orphan"
    )
    manifests = relationship(
        "DomainManifest",
        back_populates="domain",
        cascade="all, delete-orphan",
    )


class Prompt(Base):
    """A single prompt / instruction block for a given domain."""

    __tablename__ = "prompts"
    __table_args__ = (
        UniqueConstraint("domain_id", "name", name="uq_prompt_domain_name"),
    )

    id = Column(Integer, primary_key=True, index=True)
    domain_id = Column(
        Integer,
        ForeignKey("domains.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(100), nullable=False)
    text = Column(Text, nullable=False)
    is_default = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.now())
    updated_at = Column(DateTime, default=datetime.now(), onupdate=datetime.now())

    domain = relationship("Domain", back_populates="prompts")
