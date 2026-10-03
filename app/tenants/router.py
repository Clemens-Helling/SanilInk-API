from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_tenant_db
from app.core.security import get_current_token_payload
from app.core.dependencys import require_admin
from app.tenants.models import Building
from app.tenants.schemas import BuildingCreate, BuildingResponse

router = APIRouter()


@router.get("/")
async def say_hello():
    return {"message": "Hello from tenants router!"}


@router.get("/buildings", response_model=list[BuildingResponse])
async def get_buildings(
    payload: dict = Depends(get_current_token_payload),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Get all buildings for the current tenant."""
    tenant_id = payload["tenant_id"]
    result = await db.execute(select(Building).where(Building.customer_id == tenant_id))
    return result.scalars().all()


@router.get("/buildings/{building_id}", response_model=BuildingResponse | None)
async def get_building(
    building_id: int,
    payload: dict = Depends(get_current_token_payload),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Get a specific building by ID for the current tenant."""
    tenant_id = payload["tenant_id"]
    result = await db.execute(
        select(Building).where(
            Building.customer_id == tenant_id, Building.building_id == building_id
        )
    )
    return result.scalars().first()


@router.post("/buildings", response_model=BuildingResponse)
async def create_building(
    building: BuildingCreate,
    payload: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Create a new building for the current tenant."""
    tenant_id = payload["tenant_id"]
    db_building = Building(
        building_name=building.building_name,
        street=building.street,
        house_number=building.house_number,
        postal_code=building.postal_code,
        city=building.city,
        country_code=building.country_code,
        address_additional=building.address_additional,
        customer_id=tenant_id,
    )
    db.add(db_building)
    await db.commit()
    await db.refresh(db_building)
    return db_building


@router.put("/buildings/{building_id}", response_model=BuildingResponse)
async def update_building(
    building_id: int,
    building: BuildingCreate,
    payload: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Update a specific building by ID for the current tenant."""
    tenant_id = payload["tenant_id"]
    result = await db.execute(
        select(Building).where(
            Building.customer_id == tenant_id, Building.building_id == building_id
        )
    )
    db_building = result.scalars().first()
    if not db_building:
        raise HTTPException(status_code=404, detail="Building not found")
    db_building.building_name = building.building_name
    db_building.street = building.street
    db_building.house_number = building.house_number
    db_building.postal_code = building.postal_code
    db_building.city = building.city
    db_building.country_code = building.country_code
    db_building.address_additional = building.address_additional
    await db.commit()
    await db.refresh(db_building)
    return db_building


@router.delete("/buildings/{building_id}")
async def delete_building(
    building_id: int,
    payload: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Delete a specific building by ID for the current tenant."""
    tenant_id = payload["tenant_id"]
    result = await db.execute(
        select(Building).where(
            Building.customer_id == tenant_id, Building.building_id == building_id
        )
    )
    db_building = result.scalars().first()
    if not db_building:
        raise HTTPException(status_code=404, detail="Building not found")
    await db.delete(db_building)
    await db.commit()
    return {"message": "Building deleted successfully"}
