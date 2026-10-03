from app.main import app
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