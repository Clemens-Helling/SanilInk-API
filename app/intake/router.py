import base64

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.aid_kits.models import FirstAidKit
from app.core.database import get_db, get_tenant_db
from app.core.security import get_current_token_payload
from app.intake.models import IntakeKey
from app.intake.schemas import (
    IntakeKeyCreate,
    IntakeKeyResponse,
    IntakeSubmitRequest,
    IntakeSubmitResponse,
    PendingIntakeResponse,
)
from app.intake.service import IntakeService, IntakeServiceError

router = APIRouter()


@router.get("/keys", response_model=list[IntakeKeyResponse])
async def list_intake_keys(
    kit_id: int | None = Query(default=None, gt=0),
    payload: dict = Depends(get_current_token_payload),
    db: AsyncSession = Depends(get_tenant_db),
) -> list[IntakeKeyResponse]:
    """List active intake keys for the current customer, optionally filtered by kit."""
    statement = select(IntakeKey).where(
        IntakeKey.customer_id == payload["customer_id"],
        IntakeKey.revoked_at.is_(None),
    )
    if kit_id is not None:
        statement = statement.where(IntakeKey.kit_id == kit_id)
    result = await db.execute(statement.order_by(IntakeKey.created_at.desc()))
    return [IntakeKeyResponse.model_validate(key) for key in result.scalars().all()]


@router.post(
    "/keys", response_model=IntakeKeyResponse, status_code=status.HTTP_201_CREATED
)
async def create_intake_key(
    intake_key_create: IntakeKeyCreate,
    payload: dict = Depends(get_current_token_payload),
    db: AsyncSession = Depends(get_tenant_db),
) -> IntakeKeyResponse:
    """Create a QR-code intake key for a tenant.

    This endpoint is used by authenticated staff to register a new public intake key
    that can later receive anonymous sealed submissions from non-logged-in users.
    """
    result = await db.execute(
        select(FirstAidKit.kit_id).where(
            FirstAidKit.kit_id == intake_key_create.kit_id,
            FirstAidKit.customer_id == payload["customer_id"],
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Aid kit not found")

    existing_result = await db.execute(
        select(IntakeKey.intake_key_id).where(
            IntakeKey.customer_id == payload["customer_id"],
            IntakeKey.kit_id == intake_key_create.kit_id,
            IntakeKey.revoked_at.is_(None),
        )
    )
    if existing_result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This aid kit already has an active intake key",
        )

    key = await IntakeService.create_intake_key(
        db,
        customer_id=payload["customer_id"],
        kit_id=intake_key_create.kit_id,
        created_by=payload["user_id"],
        label=intake_key_create.label,
        public_key=intake_key_create.public_key,
        encrypted_private_key=intake_key_create.encrypted_private_key,
    )
    return IntakeKeyResponse(
        intake_key_id=key.intake_key_id,
        customer_id=key.customer_id,
        kit_id=key.kit_id,
        label=key.label,
        public_key=key.public_key,
        created_by=key.created_by,
        revoked_at=key.revoked_at,
        created_at=key.created_at,
    )


@router.post("/keys/{intake_key_id}/revoke", response_model=IntakeKeyResponse)
async def revoke_intake_key(
    intake_key_id: int,
    payload: dict = Depends(get_current_token_payload),
    db: AsyncSession = Depends(get_tenant_db),
) -> IntakeKeyResponse:
    """Revoke one key without deleting it or its already submitted intakes."""
    result = await db.execute(
        select(IntakeKey).where(
            IntakeKey.intake_key_id == intake_key_id,
            IntakeKey.customer_id == payload["customer_id"],
        )
    )
    key = result.scalar_one_or_none()
    if key is None:
        raise HTTPException(status_code=404, detail="Intake key not found")
    if key.revoked_at is None:
        key.revoked_at = func.now()
        await db.commit()
        await db.refresh(key)
    return IntakeKeyResponse.model_validate(key)


@router.get("/pending", response_model=list[PendingIntakeResponse])
async def list_pending_intakes(
    payload: dict = Depends(get_current_token_payload),
    db: AsyncSession = Depends(get_tenant_db),
) -> list[PendingIntakeResponse]:
    """List all anonymous submissions awaiting staff review for the tenant.

    The payloads are encrypted on the client side and therefore not readable by the server.
    This endpoint is intended for authenticated staff to review the inbox of pending intakes.
    """
    items = await IntakeService.list_pending_intakes(
        db,
        customer_id=payload["customer_id"],
    )
    return [
        PendingIntakeResponse(
            pending_intake_id=item.pending_intake_id,
            intake_key_id=item.intake_key_id,
            sealed_payload=base64.b64encode(item.sealed_payload).decode("ascii"),
            public_key=item.intake_key.public_key,
            encrypted_private_key=item.intake_key.encrypted_private_key,
            kit_label=item.intake_key.kit.label,
            kit_location_detail=item.intake_key.kit.location_detail,
            status=item.status,
            created_at=item.created_at,
            claimed_by=item.claimed_by,
            resulting_patient_id=item.resulting_patient_id,
        )
        for item in items
    ]


@router.post(
    "/pending/{pending_intake_id}/claim",
    response_model=IntakeSubmitResponse,
)
async def claim_pending_intake(
    pending_intake_id: int,
    payload: dict = Depends(get_current_token_payload),
    db: AsyncSession = Depends(get_tenant_db),
) -> IntakeSubmitResponse:
    """Mark a tenant-scoped pending intake as claimed by the current staff member."""
    try:
        pending = await IntakeService.claim_intake(
            db,
            customer_id=payload["customer_id"],
            pending_intake_id=pending_intake_id,
            claimed_by=payload["user_id"],
        )
    except IntakeServiceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return IntakeSubmitResponse(
        pending_intake_id=pending.pending_intake_id,
        status=pending.status,
    )


@router.post(
    "/{intake_key_id}/submit",
    response_model=IntakeSubmitResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_anonymous_intake(
    intake_key_id: int,
    intake_submit: IntakeSubmitRequest,
    db: AsyncSession = Depends(get_db),
) -> IntakeSubmitResponse:
    """Accept an anonymous sealed intake submission for a public intake key.

    This endpoint is intentionally unauthenticated: a person without account can submit
    encrypted data to a QR-code-backed intake key. The server stores only the sealed payload.
    """
    try:
        pending = await IntakeService.submit_anonymous_intake(
            db,
            intake_key_id=intake_key_id,
            sealed_payload=intake_submit.sealed_payload,
        )
        return IntakeSubmitResponse(
            pending_intake_id=pending.pending_intake_id,
            status=pending.status,
        )
    except IntakeServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
