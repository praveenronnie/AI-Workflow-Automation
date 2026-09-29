from backend.database.base import Base, engine, AsyncSessionLocal, get_db
from backend.database import models


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Dev convenience: drop the LEGACY global content-hash unique index.
        # Dedup is org-scoped now (uq_documents_org_hash_active); create_all
        # never drops old indexes, and the leftover global index would reject
        # a second org uploading identical content. Production should use
        # Alembic migrations instead of this guard.
        try:
            from sqlalchemy import text

            await conn.execute(
                text("DROP INDEX IF EXISTS uq_documents_content_hash_active")
            )
            await conn.execute(
                text(
                    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS org_id VARCHAR(36)"
                )
            )
            await conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_documents_org_hash_active "
                    "ON documents (org_id, content_hash) WHERE deleted_at IS NULL"
                )
            )
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_documents_org_id ON documents (org_id)"
                )
            )
        except Exception:
            pass  # non-postgres dev backends simply don't have these objects
