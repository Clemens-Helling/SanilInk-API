import base64
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import Base
from app.intake.models import IntakeKey, PendingIntake
from app.intake.router import revoke_intake_key
from app.intake.service import IntakeService, IntakeServiceError
from app.intake.schemas import (
    IntakeKeyCreate,
    IntakeKeyResponse,
    IntakePromotionRequest,
)


def test_anonymous_intake_tables_exist_in_metadata():
    table_names = {table.name for table in Base.metadata.tables.values()}

    assert "intake_keys" in table_names
    assert "pending_intakes" in table_names

    intake_keys = Base.metadata.tables["intake_keys"]
    pending_intakes = Base.metadata.tables["pending_intakes"]

    assert "intake_key_id" in intake_keys.columns
    assert "public_key" in intake_keys.columns
    assert "encrypted_private_key" in intake_keys.columns
    assert "revoked_at" in intake_keys.columns

    assert "pending_intake_id" in pending_intakes.columns
    assert "intake_key_id" in pending_intakes.columns
    assert "sealed_payload" in pending_intakes.columns
    assert "status" in pending_intakes.columns


def test_intake_key_schema_requires_kit_id():
    key = IntakeKeyCreate(
        kit_id=5,
        label="Werkstatt",
        public_key="p" * 40,
        encrypted_private_key="e" * 100,
    )

    assert key.kit_id == 5
    assert "kit_id" in IntakeKeyResponse.model_fields


def test_create_intake_key_persists_kit_association():
    db = MagicMock(spec=AsyncSession)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    key = asyncio.run(
        IntakeService.create_intake_key(
            db,
            customer_id=17,
            kit_id=5,
            created_by=2,
            label="Werkstatt",
            public_key="p" * 40,
            encrypted_private_key="e" * 100,
        )
    )

    assert key.customer_id == 17
    assert key.kit_id == 5
    assert key.created_by == 2
    db.add.assert_called_once_with(key)
    db.commit.assert_awaited_once()


def test_anonymous_intake_uses_customer_of_key_not_a_fixed_customer():
    db = MagicMock(spec=AsyncSession)
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    key = MagicMock(spec=IntakeKey)
    key.intake_key_id = 41
    key.customer_id = 17
    result = MagicMock()
    result.scalar_one_or_none.return_value = key
    db.execute.return_value = result

    pending = asyncio.run(
        IntakeService.submit_anonymous_intake(
            db,
            intake_key_id=41,
            sealed_payload=base64.b64encode(b"ciphertext" * 10).decode("ascii"),
        )
    )

    assert isinstance(pending, PendingIntake)
    assert pending.customer_id == 17
    assert pending.intake_key_id == 41
    assert pending.sealed_payload == b"ciphertext" * 10
    db.commit.assert_awaited_once()


def test_anonymous_intake_rejects_missing_or_revoked_key():
    db = MagicMock(spec=AsyncSession)
    db.execute = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result

    with pytest.raises(IntakeServiceError, match="not found or revoked"):
        asyncio.run(
            IntakeService.submit_anonymous_intake(
                db,
                intake_key_id=41,
                sealed_payload=base64.b64encode(b"ciphertext" * 10).decode("ascii"),
            )
        )

    db.add.assert_not_called()
    db.commit.assert_not_awaited()


def test_promote_intake_creates_patient_and_claims_intake_atomically():
    db = MagicMock(spec=AsyncSession)
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.flush = AsyncMock()
    pending = MagicMock(spec=PendingIntake)
    pending.status = "pending"
    pending.claimed_by = None
    pending.claimed_at = None
    pending.resulting_patient_id = None
    result = MagicMock()
    result.scalar_one_or_none.return_value = pending
    db.execute.return_value = result
    db.flush.side_effect = lambda: setattr(
        db.add.call_args.args[0], "patient_id", 22
    )
    patient_data = IntakePromotionRequest(
        encrypted_real_name="a" * 60,
        encrypted_real_last_name="b" * 60,
        encrypted_birth_day="c" * 60,
        encrypted_intake_description="d" * 60,
        encrypted_initial_measures="e" * 60,
        encrypted_witnesses="f" * 60,
    )

    claimed, patient = asyncio.run(
        IntakeService.promote_intake(
            db,
            customer_id=17,
            pending_intake_id=9,
            claimed_by=2,
            patient_data=patient_data,
        )
    )

    statement = db.execute.await_args.args[0]
    assert "pending_intakes.customer_id = :customer_id_1" in str(statement)
    assert "FOR UPDATE" in str(statement)
    assert claimed.status == "claimed"
    assert claimed.claimed_by == 2
    assert claimed.claimed_at is not None
    assert claimed.resulting_patient_id == 22
    assert patient.patient_id == 22
    assert patient.customer_id == 17
    assert patient.encrypted_initial_measures == "e" * 60
    db.add.assert_called_once_with(patient)
    db.flush.assert_awaited_once()
    db.commit.assert_awaited_once()


def test_revoke_intake_key_is_customer_scoped_and_preserves_key():
    db = MagicMock(spec=AsyncSession)
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    key = MagicMock(spec=IntakeKey)
    key.intake_key_id = 41
    key.customer_id = 17
    key.kit_id = 5
    key.label = "Werkstatt"
    key.public_key = "p" * 44
    key.created_by = 2
    key.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    key.revoked_at = None
    result = MagicMock()
    result.scalar_one_or_none.return_value = key
    db.execute.return_value = result
    db.refresh = AsyncMock(
        side_effect=lambda refreshed: setattr(
            refreshed, "revoked_at", datetime.now(timezone.utc)
        )
    )

    response = asyncio.run(revoke_intake_key(41, {"customer_id": 17}, db))

    statement = db.execute.await_args.args[0]
    assert "intake_keys.customer_id = :customer_id_1" in str(statement)
    assert response.intake_key_id == 41
    assert response.revoked_at is not None
    db.commit.assert_awaited_once()


def test_revoke_intake_key_returns_404_for_another_customer():
    db = MagicMock(spec=AsyncSession)
    db.execute = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result

    with pytest.raises(HTTPException) as error:
        asyncio.run(revoke_intake_key(41, {"customer_id": 17}, db))

    assert error.value.status_code == 404
    db.commit.assert_not_awaited()
