import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.invite.models import PendingRegistration, RegistrationStatus
from app.invite.service import PendingRegistrationService
from app.tenants.models import Tenant
from app.users.models import CustomerKeySlot, User, UserKey


@pytest.mark.asyncio
async def test_grant_pending_invite_creates_key_slot_and_marks_active():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
            CREATE TABLE customers (
                customer_id INTEGER PRIMARY KEY,
                customer_number VARCHAR(100) NOT NULL UNIQUE,
                contact_person_first_name VARCHAR(255),
                contact_person_last_name VARCHAR(255),
                email VARCHAR(100),
                phone_number VARCHAR(100)
            )
        """
            )
        )
        await conn.execute(
            text(
                """
            CREATE TABLE users (
                "User_ID" INTEGER PRIMARY KEY,
                customer INTEGER NOT NULL REFERENCES customers(customer_id),
                name VARCHAR(255),
                last_name VARCHAR(255),
                teacher INTEGER,
                departement INTEGER,
                karten_nummer VARCHAR(255),
                permission VARCHAR(255),
                username VARCHAR(255),
                email VARCHAR(255) UNIQUE,
                is_active BOOLEAN DEFAULT TRUE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """
            )
        )
        await conn.execute(
            text(
                """
            CREATE TABLE user_keys (
                key_id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users("User_ID"),
                public_key VARCHAR NOT NULL,
                encrypted_private_key VARCHAR NOT NULL,
                argon2_salt VARCHAR(255) NOT NULL,
                argon2_time_cost_a INTEGER,
                argon2_memory_cost_a INTEGER,
                argon2_parallelism_a INTEGER,
                stored_key VARCHAR(255) NOT NULL,
                argon2_salt_b VARCHAR(255) NOT NULL,
                argon2_time_cost_b INTEGER NOT NULL,
                argon2_memory_cost_b INTEGER NOT NULL,
                argon2_parallelism_b INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE
            )
        """
            )
        )
        await conn.execute(
            text(
                """
            CREATE TABLE pending_registrations (
                registration_id INTEGER PRIMARY KEY,
                customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
                email VARCHAR(255) NOT NULL,
                invite_token_hash VARCHAR(64) NOT NULL UNIQUE,
                proposed_role VARCHAR(255),
                status VARCHAR(32) NOT NULL,
                invited_by INTEGER NOT NULL REFERENCES users("User_ID"),
                user_id INTEGER REFERENCES users("User_ID"),
                granted_by INTEGER REFERENCES users("User_ID"),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                expires_at DATETIME NOT NULL,
                registered_at DATETIME,
                granted_at DATETIME,
                revoked_at DATETIME
            )
        """
            )
        )
        await conn.execute(
            text(
                """
            CREATE TABLE customer_key_slots (
                slot_id INTEGER PRIMARY KEY,
                customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
                user_id INTEGER NOT NULL REFERENCES users("User_ID"),
                ephemeral_public_key VARCHAR(255) NOT NULL,
                encrypted_gek VARCHAR NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """
            )
        )

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        tenant = Tenant(customer_number="T-100", contact_person_first_name="A")
        db.add(tenant)
        await db.flush()

        inviter = User(
            customer_id=tenant.customer_id,
            username="inviter",
            email="inviter@example.com",
            is_active=True,
        )
        invited = User(
            customer_id=tenant.customer_id,
            username="newuser",
            email="newuser@example.com",
            is_active=True,
        )
        db.add_all([inviter, invited])
        await db.flush()

        db.add(
            UserKey(
                user_id=invited.user_id,
                public_key="pub-key",
                encrypted_private_key="enc-priv",
                argon2_salt_a="salt-a",
                argon2_time_cost_a=3,
                argon2_memory_cost_a=64,
                argon2_parallelism_a=1,
                stored_key="stored-key",
                argon2_salt_b="salt-b",
                argon2_time_cost_b=3,
                argon2_memory_cost_b=64,
                argon2_parallelism_b=1,
            )
        )

        registration = PendingRegistration(
            customer_id=tenant.customer_id,
            email=invited.email,
            invite_token_hash="hash",
            status=RegistrationStatus.AWAITING_KEY_GRANT,
            invited_by=inviter.user_id,
            user_id=invited.user_id,
            expires_at=__import__("datetime").datetime.utcnow(),
        )
        db.add(registration)
        await db.flush()

        slot = await PendingRegistrationService.grant_invite(
            db,
            registration_id=registration.registration_id,
            customer_id=tenant.customer_id,
            granting_user_id=inviter.user_id,
            ephemeral_public_key="ephemeral-pub",
            encrypted_gek="encrypted-gek",
        )

        assert slot.user_id == invited.user_id
        assert slot.customer_id == tenant.customer_id
        assert slot.ephemeral_public_key == "ephemeral-pub"
        assert slot.encrypted_gek == "encrypted-gek"

        await db.refresh(registration)
        assert registration.status == RegistrationStatus.ACTIVE
        assert registration.granted_by == inviter.user_id
        assert registration.granted_at is not None

    await engine.dispose()
