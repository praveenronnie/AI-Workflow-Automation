"""Minimal CRUD endpoints for *domains* and their *prompts*.

These endpoints are intentionally separate from ``report_routes.py`` so the
report pipeline is never touched while we make the extension platform /
domain agnostic.

Current scope (MVP):
    * List / create domains (public – this is *configuration* data).
    * List / create prompts for a given domain.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from inspection_ai.database.base import get_db
from inspection_ai.database.models.domain import Domain, Prompt
from inspection_ai.database.models.domain_manifest import (
    DomainManifest,
    DomainSection,
    DomainField,
)
from inspection_ai.features.schemas import (
    DomainCreate,
    DomainOut,
    DomainUpdate,
    DomainUploadIn,
    DomainUploadOut,
    PromptCreate,
    PromptOut,
    DomainManifestIn,
    DomainManifestOut,
)

router = APIRouter(prefix="/domains", tags=["domains"])


# --------------------------------------------------------------------------- #
# /domains                                                                     #
# --------------------------------------------------------------------------- #
@router.get("/", response_model=List[DomainOut])
async def list_domains(
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
):
    """Return every domain registered in the system.

    `active_only` defaults to True – pass `active_only=false` to fetch the
    full list (handy for admin UIs during migration phases).
    """
    stmt = select(Domain)
    if active_only:
        stmt = stmt.where(Domain.is_active == 1)
    stmt = stmt.order_by(Domain.name)
    result = await db.execute(stmt)
    domains = result.scalars().all()
    return domains or []


@router.post("/", response_model=DomainOut, status_code=status.HTTP_201_CREATED)
async def create_domain(
    domain_in: DomainCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new domain if `name` is not already taken."""
    exists = await db.execute(
        select(Domain).where(func.lower(Domain.name) == func.lower(domain_in.name))
    )
    if exists.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Domain named '{domain_in.name}' already exists.",
        )

    domain = Domain(**domain_in.model_dump())
    db.add(domain)
    await db.commit()
    await db.refresh(domain)
    return domain


# --------------------------------------------------------------------------- #
# /domains/upload  (composite: domain identity + full section/field tree)      #
# --------------------------------------------------------------------------- #
@router.post(
    "/upload",
    response_model=DomainUploadOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_domain_bundle(
    payload: DomainUploadIn,
    db: AsyncSession = Depends(get_db),
):
    # --- upsert domain -------------------------------------------------------
    result = await db.execute(
        select(Domain).where(func.lower(Domain.name) == func.lower(payload.domain_name))
    )
    domain = result.scalar_one_or_none()
    if domain is None:
        domain = Domain(
            name=payload.domain_name,
            display_name=payload.display_name,
            description=payload.description,
            version=payload.version,
            is_active=1 if payload.is_active else 0,
        )
        db.add(domain)
        await db.flush()
    else:
        domain.display_name = payload.display_name or domain.display_name
        domain.description = payload.description or domain.description
        domain.version = payload.version
        domain.is_active = 1 if payload.is_active else 0

    # --- create-or-replace manifest for this version --------------------------
    existing = await db.execute(
        select(DomainManifest).where(
            DomainManifest.domain_id == domain.id,
            DomainManifest.version == payload.version,
        )
    )
    manifest = existing.scalar_one_or_none()
    if manifest:
        await db.delete(manifest)
        await db.flush()

    field_count = sum(len(s.fields) for s in payload.sections)
    manifest = DomainManifest(
        domain_id=domain.id,
        version=payload.version,
        section_count=len(payload.sections),
        field_count=field_count,
    )
    db.add(manifest)
    await db.flush()

    for index, section_in in enumerate(payload.sections):
        db.add(build_section_row(manifest, section_in, index))

    await db.commit()
    await db.refresh(manifest)

    return DomainUploadOut(
        domain_id=domain.id,
        manifest_id=manifest.id,
        domain_name=domain.name,
        version=manifest.version,
        section_count=manifest.section_count or len(payload.sections),
        field_count=manifest.field_count or field_count,
    )


@router.get("/{domain_id}", response_model=DomainOut)
async def get_domain(domain_id: int, db: AsyncSession = Depends(get_db)):
    domain = await db.get(Domain, domain_id)
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    return domain


@router.put("/{domain_id}", response_model=DomainOut)
async def update_domain(
    domain_id: int,
    domain_in: DomainUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Partially update a domain (name/description/version/is_active)."""
    domain = await db.get(Domain, domain_id)
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    data = domain_in.model_dump(exclude_unset=True)

    new_name = data.get("name")
    if new_name and new_name.lower() != domain.name.lower():
        exists = await db.execute(
            select(Domain).where(
                func.lower(Domain.name) == func.lower(new_name),
                Domain.id != domain_id,
            )
        )
        if exists.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Domain named '{new_name}' already exists.",
            )

    if "is_active" in data and data["is_active"] is not None:
        data["is_active"] = 1 if data["is_active"] else 0

    for key, value in data.items():
        setattr(domain, key, value)

    await db.commit()
    await db.refresh(domain)
    return domain


@router.delete("/{domain_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_domain(domain_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a domain and (via CASCADE) its manifests, sections and fields."""
    domain = await db.get(Domain, domain_id)
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    await db.delete(domain)
    await db.commit()
    return None


# --------------------------------------------------------------------------- #
# /domains/{id}/prompts                                                        #
# --------------------------------------------------------------------------- #
@router.get("/{domain_id}/prompts", response_model=List[PromptOut])
async def list_prompts(domain_id: int, db: AsyncSession = Depends(get_db)):
    domain = await db.get(Domain, domain_id)
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    result = await db.execute(
        select(Prompt).where(Prompt.domain_id == domain_id).order_by(Prompt.name)
    )
    return result.scalars().all() or []


@router.post(
    "/{domain_id}/prompts",
    response_model=PromptOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_prompt(
    domain_id: int,
    prompt_in: PromptCreate,
    db: AsyncSession = Depends(get_db),
):
    domain = await db.get(Domain, domain_id)
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    # PromptCreate carries its own domain_id – enforce consistency.
    if prompt_in.domain_id != domain_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Domain ID mismatch.",
        )

    prompt = Prompt(**prompt_in.model_dump())
    db.add(prompt)
    await db.commit()
    await db.refresh(prompt)
    return prompt


# --------------------------------------------------------------------------- #
# /domains/{id}/manifests                                                      #
# --------------------------------------------------------------------------- #
def build_section_row(
    manifest: DomainManifest, section_in, order: int
) -> DomainSection:
    section = DomainSection(
        manifest_id=manifest.id,
        name=section_in.name,
        aliases=section_in.aliases or [],
        order=order,
    )
    for field_in in section_in.fields:
        section.fields.append(
            DomainField(
                name=field_in.name,
                aliases=field_in.aliases or [],
                intent=field_in.intent,
                description=field_in.description,
            )
        )
    return section


@router.post(
    "/{domain_id}/manifests",
    response_model=DomainManifestOut,
    status_code=status.HTTP_201_CREATED,
)
async def store_domain_manifest(
    domain_id: int,
    manifest_in: DomainManifestIn,
    db: AsyncSession = Depends(get_db),
):
    """Create or replace the manifest tree (sections -> fields) for a domain version."""
    domain = await db.get(Domain, domain_id)
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    existing = await db.execute(
        select(DomainManifest).where(
            DomainManifest.domain_id == domain_id,
            DomainManifest.version == manifest_in.version,
        )
    )
    manifest = existing.scalar_one_or_none()
    if manifest:
        await db.delete(manifest)
        await db.flush()

    manifest = DomainManifest(
        domain_id=domain_id,
        version=manifest_in.version,
        section_count=len(manifest_in.sections),
        field_count=sum(len(s.fields) for s in manifest_in.sections),
    )
    db.add(manifest)
    await db.flush()

    for index, section_in in enumerate(manifest_in.sections):
        db.add(build_section_row(manifest, section_in, index))
    await db.commit()

    result = await db.execute(
        select(DomainManifest)
        .where(
            DomainManifest.domain_id == domain_id,
            DomainManifest.version == manifest_in.version,
        )
        .options(
            selectinload(DomainManifest.sections).selectinload(DomainSection.fields)
        )
    )
    stored = result.scalar_one()
    return stored


@router.get("/{domain_id}/manifests", response_model=DomainManifestOut)
async def get_domain_manifest(domain_id: int, db: AsyncSession = Depends(get_db)):
    """Return the most recent manifest tree for a domain."""
    domain = await db.get(Domain, domain_id)
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    result = await db.execute(
        select(DomainManifest)
        .where(DomainManifest.domain_id == domain_id)
        .order_by(DomainManifest.updated_at.desc())
        .options(
            selectinload(DomainManifest.sections).selectinload(DomainSection.fields)
        )
        .limit(1)
    )
    manifest = result.scalar_one_or_none()
    if not manifest:
        raise HTTPException(status_code=404, detail="No manifest found for this domain")
    return manifest
