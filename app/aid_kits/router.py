from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.aid_kits.models import FirstAidKit
from app.aid_kits.schemas import AidKitCreate, AidKitResponse
from app.core.database import get_tenant_db
from app.core.security import get_current_token_payload
from app.tenants.models import Building


router = APIRouter()


async def _get_kit(db: AsyncSession, customer_id: int, kit_id: int) -> FirstAidKit:
    result = await db.execute(
        select(FirstAidKit).where(
            FirstAidKit.customer_id == customer_id,
            FirstAidKit.kit_id == kit_id,
        )
    )
    kit = result.scalar_one_or_none()
    if kit is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Aid kit not found"
        )
    return kit


async def _ensure_building_belongs_to_customer(
    db: AsyncSession, customer_id: int, building_id: int
) -> None:
    result = await db.execute(
        select(Building.building_id).where(
            Building.customer_id == customer_id,
            Building.building_id == building_id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Building not found"
        )


async def _commit_or_raise_conflict(db: AsyncSession, detail: str) -> None:
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=detail
        ) from exc


@router.get("/", response_model=list[AidKitResponse])
async def get_aid_kits(
    payload: dict = Depends(get_current_token_payload),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Get all first aid kits for the current tenant."""
    customer_id = payload["customer_id"]
    result = await db.execute(
        select(FirstAidKit)
        .where(FirstAidKit.customer_id == customer_id)
        .order_by(FirstAidKit.building_id, FirstAidKit.label)
    )
    return result.scalars().all()


@router.post("/", response_model=AidKitResponse, status_code=status.HTTP_201_CREATED)
async def create_aid_kit(
    aid_kit: AidKitCreate,
    payload: dict = Depends(get_current_token_payload),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Create a new first aid kit for the current tenant."""
    customer_id = payload["customer_id"]
    await _ensure_building_belongs_to_customer(db, customer_id, aid_kit.building_id)
    db_aid_kit = FirstAidKit(
        customer_id=customer_id,
        building_id=aid_kit.building_id,
        label=aid_kit.label,
        location_detail=aid_kit.location_detail,
        is_active=aid_kit.is_active,
    )
    db.add(db_aid_kit)
    await _commit_or_raise_conflict(
        db, "An aid kit with this label already exists for this customer"
    )
    await db.refresh(db_aid_kit)
    return db_aid_kit


@router.get("/{kit_id}", response_model=AidKitResponse)
async def get_aid_kit(
    kit_id: int,
    payload: dict = Depends(get_current_token_payload),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Get a specific first aid kit by ID for the current tenant."""
    return await _get_kit(db, payload["customer_id"], kit_id)


@router.put("/{kit_id}", response_model=AidKitResponse)
async def update_aid_kit(
    kit_id: int,
    aid_kit: AidKitCreate,
    payload: dict = Depends(get_current_token_payload),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Update a specific first aid kit by ID for the current tenant."""
    customer_id = payload["customer_id"]
    db_aid_kit = await _get_kit(db, customer_id, kit_id)
    await _ensure_building_belongs_to_customer(db, customer_id, aid_kit.building_id)

    db_aid_kit.building_id = aid_kit.building_id
    db_aid_kit.label = aid_kit.label
    db_aid_kit.location_detail = aid_kit.location_detail
    db_aid_kit.is_active = aid_kit.is_active

    await _commit_or_raise_conflict(
        db, "An aid kit with this label already exists for this customer"
    )
    await db.refresh(db_aid_kit)
    return db_aid_kit


@router.delete("/{kit_id}")
async def delete_aid_kit(
    kit_id: int,
    payload: dict = Depends(get_current_token_payload),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Delete a specific first aid kit by ID for the current tenant."""
    db_aid_kit = await _get_kit(db, payload["customer_id"], kit_id)

    await db.delete(db_aid_kit)
    await _commit_or_raise_conflict(
        db, "The aid kit cannot be deleted because it is referenced by other records"
    )
    return {"message": "Aid kit deleted successfully"}
