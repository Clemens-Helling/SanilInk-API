import asyncio
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.tenants.router import create_building, get_buildings
from app.tenants.schemas import BuildingCreate


def test_building_routes_have_valid_request_and_response_models():
    schema = app.openapi()
    building_create = schema["components"]["schemas"]["BuildingCreate"]

    assert building_create["required"] == [
        "building_name",
        "street",
        "house_number",
        "postal_code",
        "city",
    ]
    assert "/tenants/buildings" in schema["paths"]


def test_building_create_defaults_country_code():
    building = BuildingCreate(
        building_name="Main office",
        street="Example Street",
        house_number="1",
        postal_code="12345",
        city="Berlin",
    )

    assert building.country_code == "DE"


def test_get_buildings_uses_customer_id_from_access_token():
    db = MagicMock(spec=AsyncSession)
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=result)

    buildings = asyncio.run(get_buildings({"customer_id": 17}, db))

    statement = db.execute.await_args.args[0]
    assert "buildings.customer_id = :customer_id_1" in str(statement)
    assert 17 in statement.compile().params.values()
    assert buildings == []


def test_create_building_uses_customer_id_from_admin_token():
    db = MagicMock(spec=AsyncSession)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    building_request = BuildingCreate(
        building_name="Main office",
        street="Example Street",
        house_number="1",
        postal_code="12345",
        city="Berlin",
    )

    building = asyncio.run(
        create_building(
            building_request,
            {"customer_id": 17, "user_id": 2},
            db,
        )
    )

    assert building.customer_id == 17
    assert building.building_name == "Main office"
    db.add.assert_called_once_with(building)
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(building)