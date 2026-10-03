from fastapi import APIRouter, Depends  #

from app.aid_kits.schemas import AidKitCreate, AidKitResponse
from app.core.database import get_tenant_db
from app.core.security import get_current_token_payload
from app.aid_kits.models import FirstAidKit
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

router = APIRouter()


@router.get("/")
async def get_aid_kits(
    payload: dict = Depends(get_current_token_payload),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Get all first aid kits for the current tenant."""
    tenant_id = payload["tenant_id"]
    result = await db.execute(
        select(FirstAidKit).where(FirstAidKit.tenant_id == tenant_id)
    )
    return result.scalars().all()


@router.post("/")
async def create_aid_kit(
    aid_kit: AidKitCreate,
    payload: dict = Depends(get_current_token_payload),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Create a new first aid kit for the current tenant."""
    tenant_id = payload["tenant_id"]
    db_aid_kit = FirstAidKit(
        name=aid_kit.name,
        description=aid_kit.description,
        building_id=aid_kit.building_id,
        label=aid_kit.label,
        location=aid_kit.location,
        is_active=aid_kit.is_active,
        created_at=aid_kit.created_at,
        tenant_id=tenant_id,
    )
    db.add(db_aid_kit)
    await db.commit()
    await db.refresh(db_aid_kit)
    return db_aid_kit


@router.get("/{kit_id}")
async def get_aid_kit(
    kit_id: int,
    payload: dict = Depends(get_current_token_payload),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Get a specific first aid kit by ID for the current tenant."""
    tenant_id = payload["tenant_id"]
    result = await db.execute(
        select(FirstAidKit).where(
            FirstAidKit.tenant_id == tenant_id, FirstAidKit.kit_id == kit_id
        )
    )
    aid_kit = result.scalar_one_or_none()
    if aid_kit is None:
        return {"error": "Aid kit not found"}
    return AidKitResponse(
        id=aid_kit.kit_id,
        name=aid_kit.name,
        description=aid_kit.description,
        building_id=aid_kit.building_id,
        label=aid_kit.label,
        location=aid_kit.location,
        is_active=aid_kit.is_active,
        created_at=aid_kit.created_at,
    )


@router.put("/{kit_id}")
async def update_aid_kit(
    kit_id: int,
    aid_kit: AidKitCreate,
    payload: dict = Depends(get_current_token_payload),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Update a specific first aid kit by ID for the current tenant."""
    tenant_id = payload["tenant_id"]
    result = await db.execute(
        select(FirstAidKit).where(
            FirstAidKit.tenant_id == tenant_id, FirstAidKit.kit_id == kit_id
        )
    )
    db_aid_kit = result.scalar_one_or_none()
    if db_aid_kit is None:
        return {"error": "Aid kit not found"}

    db_aid_kit.name = aid_kit.name
    db_aid_kit.description = aid_kit.description
    db_aid_kit.building_id = aid_kit.building_id
    db_aid_kit.label = aid_kit.label
    db_aid_kit.location = aid_kit.location
    db_aid_kit.is_active = aid_kit.is_active
    db_aid_kit.created_at = aid_kit.created_at

    await db.commit()
    await db.refresh(db_aid_kit)
    return db_aid_kit


@router.delete("/{kit_id}")
async def delete_aid_kit(
    kit_id: int,
    payload: dict = Depends(get_current_token_payload),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Delete a specific first aid kit by ID for the current tenant."""
    tenant_id = payload["tenant_id"]
    result = await db.execute(
        select(FirstAidKit).where(
            FirstAidKit.tenant_id == tenant_id, FirstAidKit.kit_id == kit_id
        )
    )
    db_aid_kit = result.scalar_one_or_none()
    if db_aid_kit is None:
        return {"error": "Aid kit not found"}

    await db.delete(db_aid_kit)
    await db.commit()
    return {"message": "Aid kit deleted successfully"}
