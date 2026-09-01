import datetime
import secrets
import hashlib
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from app.users.models import CustomerKeySlot, User, UserKey
from app.invite.exeptions import DuplicateInviteError, InvalidInviteTokenError
from app.invite.models import PendingRegistration, RegistrationStatus
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import selectinload
from sqlalchemy import select


def _utc_naive_now() -> datetime:
    """Return a UTC timestamp without tzinfo to match PostgreSQL TIMESTAMP WITHOUT TIME ZONE columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class PendingRegistrationServiceError(Exception):
    pass


class PendingRegistrationService:
    @staticmethod
    async def create_invite(
        db: AsyncSession,
        *,
        email: str,
        customer_id: int,
        invited_by: int,
        proposed_role: str | None = None,
        expires_in: timedelta = timedelta(days=7),
    ) -> tuple[str, PendingRegistration]:

        invite_token, invite_token_hash = (
            await PendingRegistrationService._generate_invite_token()
        )  # sync, kein await nötig

        pending_registration = PendingRegistration(
            customer_id=customer_id,
            email=email,
            invite_token_hash=invite_token_hash,
            proposed_role=proposed_role,
            invited_by=invited_by,
            expires_at=_utc_naive_now() + expires_in,
        )
        db.add(pending_registration)

        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise DuplicateInviteError(
                f"Es existiert bereits ein offener Invite für {email} in diesem Tenant."
            )

        await db.refresh(pending_registration)
        return invite_token, pending_registration

    @staticmethod
    async def revoke_invite(db: AsyncSession, *, registration_id: int) -> None:
        result = await db.execute(
            select(PendingRegistration).where(
                PendingRegistration.registration_id == registration_id
            )
        )
        pending_registration = result.scalar_one_or_none()
        if not pending_registration:
            raise PendingRegistrationServiceError(
                f"Pending registration with ID {registration_id} not found."
            )
        pending_registration.status = "revoked"
        pending_registration.revoked_at = _utc_naive_now()
        await db.commit()

    @staticmethod
    async def _hash_invite_token(token: str) -> str:
        # Hash the invite token using SHA256
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    async def _generate_invite_token() -> tuple[str, str]:
        # Generate a secure random token and its SHA256 hash

        token = secrets.token_urlsafe(32)  # Generate a secure random token
        token_hash = await PendingRegistrationService._hash_invite_token(
            token
        )  # Hash the token
        return token, token_hash

    @staticmethod
    async def validate_invite_token(
        db: AsyncSession, token: str, load_customer: bool = False
    ) -> PendingRegistration:
        """
        Prüft einen Invite-Token OHNE Zustand zu verändern (reiner Read).
        Wird sowohl vom Pre-Check-Endpoint als auch von register() aufgerufen.

        load_customer: Wenn True, eager-loaded die customer relationship.
        """
        token_hash = await PendingRegistrationService._hash_invite_token(token)

        query = select(PendingRegistration).where(
            PendingRegistration.invite_token_hash == token_hash
        )
        if load_customer:
            query = query.options(selectinload(PendingRegistration.customer))

        result = await db.execute(query)
        registration = result.scalar_one_or_none()

        if registration is None:
            raise InvalidInviteTokenError("Invite-Link ist ungültig.")

        if registration.status != RegistrationStatus.INVITED:
            raise InvalidInviteTokenError(
                "Invite-Link wurde bereits verwendet oder widerrufen."
            )

        if registration.expires_at < _utc_naive_now():
            raise InvalidInviteTokenError("Invite-Link ist abgelaufen.")

        return registration

    @staticmethod
    async def register_via_invite(
        db: AsyncSession,
        *,
        token: str,
        username: str | None,
        public_key: str,
        encrypted_private_key: str,
        argon2_salt_a: str,
        argon2_time_cost_a: int,
        argon2_memory_cost_a: int,
        argon2_parallelism_a: int,
        stored_key: str,
        argon2_salt_b: str,
        argon2_time_cost_b: int,
        argon2_memory_cost_b: int,
        argon2_parallelism_b: int,
    ) -> PendingRegistration:
        """
        Legt users- und user_keys-Eintrag an und markiert die Registration
        als awaiting_key_grant. customer_id und email kommen bewusst NICHT
        vom Client, sondern aus dem bereits validierten pending_registrations-
        Eintrag — verhindert, dass ein manipulierter Client einen anderen
        Tenant oder eine andere E-Mail unterschiebt.
        """
        # Erneute Validierung — nicht nur UI-Komfort, sondern Schutz gegen
        # TOCTOU: Zwischen Pre-Check (GET) und diesem Aufruf (POST) könnte
        # der Token revoked worden oder abgelaufen sein.
        registration = await PendingRegistrationService.validate_invite_token(db, token)

        new_user = User(
            customer_id=registration.customer_id,
            email=registration.email,
            username=username,
            is_active=True,
        )
        db.add(new_user)
        await db.flush()  # user_id wird für den FK in UserKey/PendingRegistration benötigt

        user_key = UserKey(
            user_id=new_user.user_id,
            public_key=public_key,
            encrypted_private_key=encrypted_private_key,
            argon2_salt_a=argon2_salt_a,
            argon2_time_cost_a=argon2_time_cost_a,
            argon2_memory_cost_a=argon2_memory_cost_a,
            argon2_parallelism_a=argon2_parallelism_a,
            stored_key=stored_key,
            argon2_salt_b=argon2_salt_b,
            argon2_time_cost_b=argon2_time_cost_b,
            argon2_memory_cost_b=argon2_memory_cost_b,
            argon2_parallelism_b=argon2_parallelism_b,
        )
        db.add(user_key)

        registration.user_id = new_user.user_id
        registration.status = RegistrationStatus.AWAITING_KEY_GRANT
        registration.registered_at = _utc_naive_now()

        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            # z. B. email bereits in users vergeben (falls dort UNIQUE) o. Ä.
            raise InvalidInviteTokenError(
                "Registrierung konnte nicht abgeschlossen werden."
            )

        await db.refresh(registration)
        return registration

    @staticmethod
    async def list_pending_grants(
        db: AsyncSession,
        *,
        customer_id: int,
    ) -> list[PendingRegistration]:
        result = await db.execute(
            select(PendingRegistration)
            .where(
                PendingRegistration.customer_id == customer_id,
                PendingRegistration.status == RegistrationStatus.AWAITING_KEY_GRANT,
            )
            .order_by(PendingRegistration.registered_at.desc().nullslast())
        )
        return list(result.scalars().all())

    @staticmethod
    async def grant_invite(
        db: AsyncSession,
        *,
        registration_id: int,
        customer_id: int,
        granting_user_id: int,
        ephemeral_public_key: str,
        encrypted_gek: str,
    ) -> CustomerKeySlot:
        """
        Phase 3 des Invite-Flows: Ein aktives Tenant-Mitglied gewährt dem neu
        registrierten User den GEK-Zugriff. Der Client hat GEK bereits client-seitig
        mit dem public_key des neuen Users verschlüsselt; der Server speichert nur
        den verschlüsselten Slot und setzt den Invite auf active.
        """
        result = await db.execute(
            select(PendingRegistration)
            .where(
                PendingRegistration.registration_id == registration_id,
                PendingRegistration.customer_id == customer_id,
            )
            .with_for_update()
        )
        registration = result.scalar_one_or_none()

        if registration is None:
            raise PendingRegistrationServiceError("Invite not found for this tenant.")

        if registration.status != RegistrationStatus.AWAITING_KEY_GRANT:
            raise PendingRegistrationServiceError("Invite is not awaiting a key grant.")

        if registration.user_id is None:
            raise PendingRegistrationServiceError("Invite has no registered user yet.")

        existing_slot = await db.execute(
            select(CustomerKeySlot).where(
                CustomerKeySlot.customer_id == customer_id,
                CustomerKeySlot.user_id == registration.user_id,
            )
        )
        if existing_slot.scalar_one_or_none() is not None:
            raise PendingRegistrationServiceError(
                "GEK key slot already exists for this user."
            )

        slot = CustomerKeySlot(
            customer_id=customer_id,
            user_id=registration.user_id,
            ephemeral_public_key=ephemeral_public_key,
            encrypted_gek=encrypted_gek,
        )
        db.add(slot)

        registration.status = RegistrationStatus.ACTIVE
        registration.granted_by = granting_user_id
        registration.granted_at = _utc_naive_now()

        await db.commit()
        await db.refresh(slot)
        await db.refresh(registration)
        return slot
