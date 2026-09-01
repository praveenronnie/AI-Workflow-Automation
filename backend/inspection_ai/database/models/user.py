from datetime import datetime
import uuid

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from inspection_ai.database.base import Base

import enum


class UserRole(str, enum.Enum):
    owner = "owner"
    admin = "admin"
    member = "member"
    viewer = "viewer"


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(255))
    avatar_url = Column(Text)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False, index=True)
    email_verified = Column(Boolean, default=False)
    last_login = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    memberships = relationship("OrganizationMember", back_populates="user")

    # Many-to-many: reports this user is linked to via ``report_users``.
    # Writes go through ReportUser rows / repository methods.
    report_links = relationship(
        "ReportUser",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="ReportUser.user_id",
    )
    reports = relationship(
        "Report",
        secondary="report_users",
        viewonly=True,
        foreign_keys="[ReportUser.user_id, ReportUser.report_id]",
    )


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False)
    settings = Column(Text, default="{}")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    members = relationship("OrganizationMember", back_populates="organization")


class OrganizationMember(Base):
    __tablename__ = "organization_members"
    __table_args__ = (UniqueConstraint("organization_id", "user_id", name="uq_org_user"),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.member, nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization", back_populates="members")
    user = relationship("User", back_populates="memberships")

