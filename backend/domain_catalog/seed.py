"""Idempotent startup seeding of bundled domain catalogs.

For every domain catalog shipped under ``domain_catalog/<slug>/``, build the
``POST /domains/upload`` payload and run it through the same upsert route
handler (domain + manifest + sections + fields are replaced per version), so
a fresh install always has its domains registered. Safe to run on every boot.
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models.domain import Domain
from backend.features.domains.routes import upload_domain_bundle
from backend.features.schemas import DomainUploadIn
from .loader import available_domains, build_upload_payload, load_catalog

logger = logging.getLogger(__name__)


async def seed_domain_catalogs(db: AsyncSession) -> list[str]:
    """Seed every bundled domain catalog. Returns the slugs that were ensured."""
    seeded: list[str] = []
    for slug in available_domains():
        try:
            # Catalog files may already be a complete upload payload
            # ({domain_name, display_name, version, ..., sections}) or a bare
            # section tree — normalize to the upload payload shape.
            raw = load_catalog(slug)
            if isinstance(raw, dict) and raw.get("domain_name") and raw.get("sections"):
                payload = raw
            else:
                payload = build_upload_payload(slug)
            # Skip if this exact domain+version is already present.
            existing = await db.execute(
                Domain.__table__.select().where(
                    Domain.name == payload["domain_name"]
                )
            )
            if existing.first() is not None:
                seeded.append(slug)
                continue
            await upload_domain_bundle(DomainUploadIn(**payload), db)
            logger.info(
                "[SEED] domain catalog ensured: %s (version %s)",
                payload["domain_name"],
                payload.get("version"),
            )
            seeded.append(slug)
        except Exception:  # noqa: BLE001 — seeding must never block startup
            logger.exception("[SEED] failed to seed domain catalog: %s", slug)
    return seeded
