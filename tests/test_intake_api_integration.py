from sqlalchemy.orm import configure_mappers

from app.core.database import Base
from app.main import app


def test_orm_mappers_configure():
    assert "patient" in Base.metadata.tables
    configure_mappers()


def test_intake_routes_are_registered():
    paths = {route.path for route in app.routes}

    assert "/intake/{intake_key_id}/submit" in paths
    assert "/intake/keys" in paths
    assert "/intake/pending" in paths
