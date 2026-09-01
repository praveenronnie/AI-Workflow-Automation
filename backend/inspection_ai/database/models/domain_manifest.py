from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from inspection_ai.database.base import Base


class DomainManifest(Base):
    """Summary row for one version of a domain's manifest."""

    __tablename__ = "domain_manifests"
    __table_args__ = (
        UniqueConstraint("domain_id", "version", name="uq_domain_manifest_version"),
    )

    id = Column(Integer, primary_key=True, index=True)
    domain_id = Column(
        Integer,
        ForeignKey("domains.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version = Column(String(50), nullable=False, default="1.0.0")
    section_count = Column(Integer, default=0)
    field_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    domain = relationship("Domain", back_populates="manifests")
    sections = relationship(
        "DomainSection",
        back_populates="manifest",
        cascade="all, delete-orphan",
    )


class DomainSection(Base):
    __tablename__ = "domain_sections"
    __table_args__ = (
        UniqueConstraint("manifest_id", "name", name="uq_domain_section_name"),
    )

    id = Column(Integer, primary_key=True, index=True)
    manifest_id = Column(
        Integer,
        ForeignKey("domain_manifests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(255), nullable=False)
    aliases = Column(JSON, default=list)
    order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    manifest = relationship("DomainManifest", back_populates="sections")
    fields = relationship(
        "DomainField",
        back_populates="section",
        cascade="all, delete-orphan",
    )


class DomainField(Base):
    __tablename__ = "domain_fields"
    __table_args__ = (
        UniqueConstraint("section_id", "name", name="uq_domain_field_name"),
    )

    id = Column(Integer, primary_key=True, index=True)
    section_id = Column(
        Integer,
        ForeignKey("domain_sections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(255), nullable=False)
    aliases = Column(JSON, default=list)
    intent = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    section = relationship("DomainSection", back_populates="fields")
