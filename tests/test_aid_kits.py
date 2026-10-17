import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.aid_kits.models import FirstAidKit
from app.aid_kits.router import (
    create_aid_kit,
    delete_aid_kit,
    get_aid_kit,
    get_aid_kits,
    update_aid_kit,
)
from app.aid_kits.schemas import AidKitCreate, AidKitResponse
from app.core.database import get_tenant_db
from app.core.security import get_current_token_payload
from app.main import app


def make_kit() -> FirstAidKit:
    return FirstAidKit(
        kit_id=5,
        customer_id=17,
        building_id=3,
        label="Werkstatt",
        location_detail="Eingang",
        is_active=True,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def make_db() -> MagicMock:
    db = MagicMock(spec=AsyncSession)
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    db.delete = AsyncMock()
    return db


def make_result(*, kit: FirstAidKit | None = None, scalar: int | None = None):
    result = MagicMock()
    result.scalar_one_or_none.return_value = kit if kit is not None else scalar
    result.scalars.return_value.all.return_value = [kit] if kit is not None else []
    return result


def test_list_aid_kits_is_customer_scoped_and_serializable():
    kit = make_kit()
    db = make_db()
    result = make_result(kit=kit)
    db.execute.return_value = result

    kits = asyncio.run(get_aid_kits({"customer_id": 17}, db))

    statement = db.execute.await_args.args[0]
    assert "first_aid_kits.customer_id = :customer_id_1" in str(statement)
    assert 17 in statement.compile().params.values()
    assert AidKitResponse.model_validate(kits[0]).label == "Werkstatt"


def test_create_aid_kit_uses_customer_id_and_checks_building_ownership():
    db = make_db()
    db.execute.return_value = make_result(scalar=3)
    payload = {"customer_id": 17, "user_id": 2}
    request = AidKitCreate(
        building_id=3,
        label="  Werkstatt  ",
        location_detail="Eingang",
    )

    created = asyncio.run(create_aid_kit(request, payload, db))

    stored_kit = db.add.call_args.args[0]
    assert stored_kit.customer_id == 17
    assert stored_kit.label == "Werkstatt"
    assert stored_kit.location_detail == "Eingang"
    assert not hasattr(stored_kit, "name")
    assert created is stored_kit
    assert db.commit.await_count == 1


def test_create_aid_kit_rejects_a_building_from_another_customer():
    db = make_db()
    db.execute.return_value = make_result()

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            create_aid_kit(
                AidKitCreate(building_id=3, label="Werkstatt"),
                {"customer_id": 17},
                db,
            )
        )

    assert error.value.status_code == 404
    db.add.assert_not_called()
    db.commit.assert_not_awaited()


def test_get_aid_kit_returns_404_for_a_kit_outside_customer():
    db = make_db()
    db.execute.return_value = make_result()

    with pytest.raises(HTTPException) as error:
        asyncio.run(get_aid_kit(5, {"customer_id": 17}, db))

    assert error.value.status_code == 404


def test_list_aid_kits_http_response_matches_persisted_model(monkeypatch):
    db = make_db()
    db.execute.return_value = make_result(kit=make_kit())
    monkeypatch.setitem(
        app.dependency_overrides,
        get_current_token_payload,
        lambda: {"customer_id": 17, "user_id": 2},
    )
    monkeypatch.setitem(app.dependency_overrides, get_tenant_db, lambda: db)

    response = TestClient(app).get("/aid-kits/")

    assert response.status_code == 200
    assert response.json() == [
        {
            "kit_id": 5,
            "building_id": 3,
            "label": "Werkstatt",
            "location_detail": "Eingang",
            "is_active": True,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        }
    ]


def test_update_changes_only_model_fields_and_preserves_creation_time():
    kit = make_kit()
    original_created_at = kit.created_at
    db = make_db()
    db.execute.side_effect = [make_result(kit=kit), make_result(scalar=4)]
    request = AidKitCreate(
        building_id=4,
        label="Lager",
        location_detail="Regal 2",
        is_active=False,
    )

    updated = asyncio.run(update_aid_kit(5, request, {"customer_id": 17}, db))

    assert updated.building_id == 4
    assert updated.label == "Lager"
    assert updated.location_detail == "Regal 2"
    assert updated.is_active is False
    assert updated.created_at == original_created_at
    assert db.commit.await_count == 1


def test_delete_removes_kit_and_commits():
    kit = make_kit()
    db = make_db()
    db.execute.return_value = make_result(kit=kit)

    response = asyncio.run(delete_aid_kit(5, {"customer_id": 17}, db))

    db.delete.assert_awaited_once_with(kit)
    db.commit.assert_awaited_once()
    assert response == {"message": "Aid kit deleted successfully"}
