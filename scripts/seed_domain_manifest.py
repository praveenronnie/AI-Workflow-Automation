"""Seed the pca_site_assessment domain manifest into the database.

Reads the full detail catalog (sections -> fields with aliases and intents)
from a JSON data file, upserts it into the domain_manifests /
domain_sections / domain_fields tables, then syncs the summary counts back
into the lean domain manifest JSON so the manifest and DB always agree.
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import select

from backend.inspection_ai.database.base import AsyncSessionLocal
from backend.inspection_ai.database.models.domain import Domain
from backend.inspection_ai.database.models.domain_manifest import (
    DomainManifest,
    DomainSection,
    DomainField,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOMAIN_NAME = "pca_site_assessment"
VERSION = "1.0.0"
CATALOG_PATH = (
    PROJECT_ROOT / "scripts" / "domain_catalog" / "pca_site_assessment_catalog.json"
)
MANIFEST_PATH = (
    PROJECT_ROOT
    / "openquire-ai-extension"
    / "domains"
    / "manifests"
    / "pca_site_assessment.json"
)


def read_catalog():
    raw = CATALOG_PATH.read_text(encoding="utf-8")
    return json.loads(raw)


async def upsert_domain(session, catalog):
    domain = await session.execute(select(Domain).where(Domain.name == DOMAIN_NAME))
    domain = domain.scalar_one_or_none()
    if not domain:
        domain = Domain(
            name=DOMAIN_NAME,
            description="PCA Site Assessment (ASTM E2018-style commercial property condition assessment)",
            version=VERSION,
        )
        session.add(domain)
        await session.flush()
    return domain


async def replace_manifest(session, domain, catalog):
    existing = await session.execute(
        select(DomainManifest).where(
            DomainManifest.domain_id == domain.id,
            DomainManifest.version == VERSION,
        )
    )
    manifest = existing.scalar_one_or_none()
    if manifest:
        await session.delete(manifest)
        await session.flush()
    return manifest


def build_sections(manifest, catalog):
    sections = []
    for index, section_data in enumerate(catalog):
        section = DomainSection(
            manifest_id=manifest.id,
            name=section_data["name"],
            aliases=section_data.get("aliases", []),
            order=index,
        )
        for field_data in section_data.get("fields", []):
            section.fields.append(
                DomainField(
                    name=field_data["name"],
                    aliases=field_data.get("aliases", []),
                    intent=field_data.get("intent"),
                    description=field_data.get("description"),
                )
            )
        sections.append(section)
    return sections


async def seed():
    catalog = read_catalog()
    async with AsyncSessionLocal() as session:
        domain = await upsert_domain(session, catalog)
        await replace_manifest(session, domain, catalog)
        manifest = DomainManifest(
            domain_id=domain.id,
            version=VERSION,
            section_count=len(catalog),
            field_count=sum(len(s.get("fields", [])) for s in catalog),
        )
        session.add(manifest)
        await session.flush()
        for section in build_sections(manifest, catalog):
            session.add(section)
        await session.commit()
        return domain.id, len(catalog), sum(len(s.get("fields", [])) for s in catalog)


def sync_manifest_json(section_count, field_count):
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest["sectionCount"] = section_count
    manifest["fieldCount"] = field_count
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main():
    domain_id, section_count, field_count = asyncio.run(seed())
    sync_manifest_json(section_count, field_count)
    print(
        f"Seeded {DOMAIN_NAME} id={domain_id} "
        f"sections={section_count} fields={field_count}"
    )


if __name__ == "__main__":
    main()
