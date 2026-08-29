from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, get_tenant_db
from app.core.security import get_current_token_payload
from app.intake.schemas import (
    IntakeKeyCreate,
    IntakeKeyResponse,
    IntakeSubmitRequest,
    IntakeSubmitResponse,
    PendingIntakeResponse,
)
from app.intake.service import IntakeService, IntakeServiceError

router = APIRouter()


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
    key = await IntakeService.create_intake_key(
        db,
        customer_id=payload["customer_id"],
        created_by=payload["user_id"],
        label=intake_key_create.label,
        public_key=intake_key_create.public_key,
        encrypted_private_key=intake_key_create.encrypted_private_key,
    )
    return IntakeKeyResponse(
        intake_key_id=key.intake_key_id,
        customer_id=key.customer_id,
        label=key.label,
        public_key=key.public_key,
        created_by=key.created_by,
        revoked_at=key.revoked_at,
        created_at=key.created_at,
    )


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
            status=item.status,
            created_at=item.created_at,
            claimed_by=item.claimed_by,
            resulting_patient_id=item.resulting_patient_id,
        )
        for item in items
    ]


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
            customer_id=1,
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
