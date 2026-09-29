"""org-scoped document dedup + refresh tokens

Revision ID: 0001_formiq_privacy
Revises:
Create Date: 2026-09-02

- documents.org_id column (privacy wall) + org-scoped unique dedup index
- drops the legacy global content-hash unique index
- refresh_tokens table (JWT rotation/revocation registry)
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_formiq_privacy"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- documents.org_id + index swap ---
    op.add_column(
        "documents",
        sa.Column("org_id", sa.String(length=36), nullable=True),
    )
    op.create_index("ix_documents_org_id", "documents", ["org_id"])
    op.execute("DROP INDEX IF EXISTS uq_documents_content_hash_active")
    op.create_index(
        "uq_documents_org_hash_active",
        "documents",
        ["org_id", "content_hash"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # --- refresh_tokens (rotation/revocation registry) ---
    op.create_table(
        "refresh_tokens",
        sa.Column("jti", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_revoked", "refresh_tokens", ["revoked"])


def downgrade() -> None:
    op.drop_table("refresh_tokens")
    op.drop_index("uq_documents_org_hash_active", table_name="documents")
    op.create_index(
        "uq_documents_content_hash_active",
        "documents",
        ["content_hash"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.drop_index("ix_documents_org_id", table_name="documents")
    op.drop_column("documents", "org_id")
