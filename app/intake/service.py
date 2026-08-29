from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.intake.models import IntakeKey, PendingIntake


class IntakeServiceError(Exception):
    pass


class IntakeService:
    @staticmethod
    async def create_intake_key(
        db: AsyncSession,
        *,
        customer_id: int,
        created_by: int,
        label: str,
        public_key: str,
        encrypted_private_key: str,
    ) -> IntakeKey:
        intake_key = IntakeKey(
            customer_id=customer_id,
            label=label,
            public_key=public_key,
            encrypted_private_key=encrypted_private_key,
            created_by=created_by,
        )
        db.add(intake_key)
        await db.commit()
        await db.refresh(intake_key)
        return intake_key

    @staticmethod
    async def submit_anonymous_intake(
        db: AsyncSession,
        *,
        customer_id: int,
        intake_key_id: int,
        sealed_payload: str,
    ) -> PendingIntake:
        result = await db.execute(
            select(IntakeKey).where(
                IntakeKey.intake_key_id == intake_key_id,
                IntakeKey.customer_id == customer_id,
                IntakeKey.revoked_at.is_(None),
            )
        )
        intake_key = result.scalar_one_or_none()
        if intake_key is None:
            raise IntakeServiceError("Intake key not found or revoked")

        pending = PendingIntake(
            customer_id=customer_id,
            intake_key_id=intake_key_id,
            sealed_payload=sealed_payload,
            status="pending",
        )
        db.add(pending)
        await db.commit()
        await db.refresh(pending)
        return pending

    @staticmethod
    async def list_pending_intakes(
        db: AsyncSession,
        *,
        customer_id: int,
    ) -> list[PendingIntake]:
        result = await db.execute(
            select(PendingIntake)
            .where(PendingIntake.customer_id == customer_id)
            .where(PendingIntake.status == "pending")
            .order_by(PendingIntake.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def claim_intake(
        db: AsyncSession,
        *,
        customer_id: int,
        pending_intake_id: int,
        claimed_by: int,
    ) -> PendingIntake:
        result = await db.execute(
            select(PendingIntake).where(
                PendingIntake.pending_intake_id == pending_intake_id,
                PendingIntake.customer_id == customer_id,
                PendingIntake.status == "pending",
            )
        )
        pending = result.scalar_one_or_none()
        if pending is None:
            raise IntakeServiceError("Pending intake not found")

        pending.status = "claimed"
        pending.claimed_by = claimed_by
        await db.commit()
        await db.refresh(pending)
        return pending
