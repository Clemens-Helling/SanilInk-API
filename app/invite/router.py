from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.invite.exeptions import InvalidInviteTokenError
from app.core.database import get_tenant_db, get_db
from app.core.dependencys import require_admin
from app.invite.schemas import (
    InviteCheckResponse,
    InviteCreateRequest,
    InviteCreateResponse,
    InviteGrantRequest,
    InviteGrantResponse,
    InviteRegisterRequest,
    InviteRegisterResponse,
    InviteListResponse,
    PendingRegistrationOut,
    PendingGrantListResponse,
    PendingGrantOut,
)
from app.invite.service import (
    PendingRegistrationService,
    PendingRegistrationServiceError,
)
from app.users.models import UserKey
from sqlalchemy import select

router = APIRouter()


# ============================================================================
# ADMIN ROUTES (spezifisch, müssen ZUERST kommen)
# ============================================================================


@router.post("/", response_model=InviteCreateResponse)
async def invite_user(
    request: InviteCreateRequest,
    payload: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_tenant_db),
) -> InviteCreateResponse:
    """
    Endpoint to invite a new user by email.
    """

    try:
        invite_token, pending_registration = (
            await PendingRegistrationService.create_invite(
                db=db,
                email=request.email,
                customer_id=payload["customer_id"],
                invited_by=payload["user_id"],
                proposed_role=request.proposed_role,
                expires_in=timedelta(days=request.expires_in_days),
            )
        )
        return InviteCreateResponse(
            invite_token=invite_token,
            email=request.email,
            expires_at=pending_registration.expires_at,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc


@router.get("/", response_model=InviteListResponse)
async def list_invites(
    payload: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_tenant_db),
) -> InviteListResponse:
    invites = await PendingRegistrationService.list_invites(db, customer_id=payload["customer_id"])
    return InviteListResponse(invites=[PendingRegistrationOut.model_validate(invite) for invite in invites])


@router.get("/pending-grants", response_model=PendingGrantListResponse)
async def list_pending_grants(
    payload: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Listet alle registrierten Invite-User auf, die noch einen GEK-Grant brauchen."""
    registrations = await PendingRegistrationService.list_pending_grants(
        db,
        customer_id=payload["customer_id"],
    )

    if not registrations:
        return PendingGrantListResponse(pending_grants=[])

    user_ids = [
        registration.user_id
        for registration in registrations
        if registration.user_id is not None
    ]
    user_keys_by_user_id = {}
    if user_ids:
        result = await db.execute(select(UserKey).where(UserKey.user_id.in_(user_ids)))
        for user_key in result.scalars().all():
            user_keys_by_user_id[user_key.user_id] = user_key

    pending_grants = [
        PendingGrantOut(
            registration_id=registration.registration_id,
            email=registration.email,
            user_id=registration.user_id,
            public_key=(
                user_keys_by_user_id.get(registration.user_id).public_key
                if registration.user_id in user_keys_by_user_id
                else ""
            ),
            registered_at=registration.registered_at,
        )
        for registration in registrations
    ]

    return PendingGrantListResponse(pending_grants=pending_grants)


@router.get("/{registration_id}/revoke")
async def revoke_invite(
    registration_id: int,
    payload: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_tenant_db),
):
    """
    Endpoint to revoke an existing invite.
    """
    try:
        await PendingRegistrationService.revoke_invite(
            db=db, registration_id=registration_id, customer_id=payload["customer_id"]
        )
        return {"message": f"Invitation {registration_id} revoked"}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc


@router.post("/{registration_id}/grant", response_model=InviteGrantResponse)
async def grant_invite(
    registration_id: int,
    request: InviteGrantRequest,
    payload: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Phase 3: ein berechtigtes Tenant-Mitglied verschlüsselt den GEK für den neuen User."""
    try:
        slot = await PendingRegistrationService.grant_invite(
            db,
            registration_id=registration_id,
            customer_id=payload["customer_id"],
            granting_user_id=payload["user_id"],
            ephemeral_public_key=request.ephemeral_public_key,
            encrypted_gek=request.encrypted_gek,
        )
    except PendingRegistrationServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    return InviteGrantResponse(
        registration_id=registration_id,
        status="active",
        slot_id=slot.slot_id,
    )


# ============================================================================
# PUBLIC ROUTES (generisch, müssen ZULETZT kommen)
# ============================================================================


@router.get("/{invite_token}", response_model=InviteCheckResponse)
async def check_invite(
    invite_token: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Pre-Check: validiert den Token, OHNE den Status zu verändern.
    Liefert die Daten, die das Frontend braucht, um das Registrierungs-
    formular anzuzeigen (vorausgefüllte E-Mail, Tenant-Name).
    """
    try:
        registration = await PendingRegistrationService.validate_invite_token(
            db, invite_token, load_customer=True
        )
    except InvalidInviteTokenError as e:
        raise HTTPException(status_code=410, detail=str(e))

    return InviteCheckResponse(
        email=registration.email,
        customer_name=registration.customer.customer_number,
        expires_at=registration.expires_at,
    )


@router.post(
    "/{invite_token}/register", response_model=InviteRegisterResponse, status_code=201
)
async def register_via_invite(
    invite_token: str,
    payload: InviteRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Schließt die Registrierung ab. Legt users + user_keys an, setzt
    pending_registrations.status auf awaiting_key_grant. Kein GEK-Zugriff
    an dieser Stelle — das passiert erst in Phase 3 durch ein bestehendes
    Tenant-Mitglied.
    """
    try:
        registration = await PendingRegistrationService.register_via_invite(
            db,
            token=invite_token,
            username=payload.username,
            public_key=payload.public_key,
            encrypted_private_key=payload.encrypted_private_key,
            argon2_salt_a=payload.argon2_salt_a,
            argon2_time_cost_a=payload.argon2_time_cost_a,
            argon2_memory_cost_a=payload.argon2_memory_cost_a,
            argon2_parallelism_a=payload.argon2_parallelism_a,
            stored_key=payload.stored_key,
            argon2_salt_b=payload.argon2_salt_b,
            argon2_time_cost_b=payload.argon2_time_cost_b,
            argon2_memory_cost_b=payload.argon2_memory_cost_b,
            argon2_parallelism_b=payload.argon2_parallelism_b,
        )
    except InvalidInviteTokenError as e:
        raise HTTPException(status_code=410, detail=str(e))

    return InviteRegisterResponse(
        user_id=registration.user_id,
        status=registration.status.value,
    )
