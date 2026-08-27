"""
Auth Service - Registration and Login with Zero-Knowledge Crypto.

Handles:
1. Registration: Create user, store encrypted keys, initialize GEK
2. Login Init: Generate challenge nonce, return Argon2id params
3. Login Verify: Validate SCRAM proof, issue JWT
"""

import base64
from datetime import datetime, timedelta, timezone
import jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.core.crypto import (
    generate_challenge_nonce,
    generate_keypair,
    generate_ephemeral_keypair,
    encrypt_gek_for_user,
    verify_client_proof,
    GEK_SIZE,
)
from app.core.challenge_nonce import get_nonce_store
from app.core.config import settings
from app.users.models import User, UserKey, CustomerKeySlot
from app.tenants.models import Tenant
from app.users.schemas import UserCreate, UserKeyCreate, CustomerKeySlotCreate
from app.auth.schemas import LoginInitRequest, LoginVerifyRequest, RegisterRequest


class RegistrationError(Exception):
    """Registration-related errors."""

    pass


class LoginError(Exception):
    """Login-related errors."""

    pass


class AuthService:
    """Authentication service with zero-knowledge architecture."""

    @staticmethod
    def _decode_registration_value(value: str, name: str) -> bytes:
        try:
            decoded = base64.b64decode(value, validate=True)
        except Exception as exc:
            raise RegistrationError(f"Invalid {name} encoding") from exc
        if not decoded:
            raise RegistrationError(f"Invalid {name} value")
        return decoded

    @staticmethod
    def _validate_registration_crypto_material(
        register_request: RegisterRequest,
    ) -> None:
        public_key = AuthService._decode_registration_value(
            register_request.public_key, "public_key"
        )
        ephemeral_public_key = AuthService._decode_registration_value(
            register_request.ephemeral_public_key,
            "ephemeral_public_key",
        )
        if len(public_key) != 32 or len(ephemeral_public_key) != 32:
            raise RegistrationError("Public keys must be 32 bytes")
        for field_name in (
            "encrypted_private_key",
            "stored_key",
            "argon2_salt_a",
            "argon2_salt_b",
            "encrypted_gek",
        ):
            AuthService._decode_registration_value(
                getattr(register_request, field_name), field_name
            )
        if register_request.argon2_salt_a == register_request.argon2_salt_b:
            raise RegistrationError("Argon2 salts must be different")

    @staticmethod
    async def register(
        db: AsyncSession,
        register_request: RegisterRequest,
    ) -> tuple[User, UserKey, CustomerKeySlot]:
        """
        Register a new user with cryptographic keys.

        Flow:
        1. Create or fetch tenant (customer)
        2. Create user
        3. Store encrypted keys (user_keys)
        4. Create/decrypt GEK and store in key slot (customer_key_slots)

        Args:
                db: Database session
                register_request: Registration payload with crypto material from client

        Returns:
                (user, user_key, customer_key_slot) tuple

        Raises:
                RegistrationError: If registration fails
        """
        try:
            AuthService._validate_registration_crypto_material(register_request)

            # Check if tenant exists
            result = await db.execute(
                select(Tenant).where(
                    Tenant.customer_number == register_request.customer_number
                )
            )
            tenant = result.scalar_one_or_none()

            if not tenant:
                # Create new tenant
                tenant = Tenant(
                    customer_number=register_request.customer_number,
                    contact_person_first_name=None,
                    contact_person_last_name=None,
                )
                db.add(tenant)
                await db.flush()

            # Create user
            user = User(
                customer_id=tenant.customer_id,
                username=register_request.username,
                email=register_request.email,
                first_name=register_request.first_name,
                last_name=register_request.last_name,
                is_active=True,
            )
            db.add(user)
            await db.flush()

            # Store cryptographic keys
            user_key = UserKey(
                user_id=user.user_id,
                public_key=register_request.public_key,
                encrypted_private_key=register_request.encrypted_private_key,
                argon2_salt_a=register_request.argon2_salt_a,
                argon2_time_cost_a=register_request.argon2_time_cost_a,
                argon2_memory_cost_a=register_request.argon2_memory_cost_a,
                argon2_parallelism_a=register_request.argon2_parallelism_a,
                stored_key=register_request.stored_key,
                argon2_salt_b=register_request.argon2_salt_b,
                argon2_time_cost_b=register_request.argon2_time_cost_b,
                argon2_memory_cost_b=register_request.argon2_memory_cost_b,
                argon2_parallelism_b=register_request.argon2_parallelism_b,
                is_active=True,
            )
            db.add(user_key)
            await db.flush()

            # Create GEK key slot (client already encrypted GEK under user's public key)
            customer_key_slot = CustomerKeySlot(
                customer_id=tenant.customer_id,
                user_id=user.user_id,
                ephemeral_public_key=register_request.ephemeral_public_key,
                encrypted_gek=register_request.encrypted_gek,
            )
            db.add(customer_key_slot)
            await db.flush()

            await db.commit()

            return user, user_key, customer_key_slot

        except Exception as e:
            await db.rollback()
            raise RegistrationError(f"Registration failed: {str(e)}")

    @staticmethod
    async def login_init(
        db: AsyncSession,
        login_init_request: LoginInitRequest,
    ) -> tuple[str, str, int, int, int, int]:
        """
        Step 1 of SCRAM login: Generate challenge nonce and return Argon2id params.

        Args:
                db: Database session
                login_init_request: Email and customer_number

        Returns:
                (challenge_nonce_b64, argon2_salt_b_b64, time_cost, memory_cost, parallelism)

        Raises:
                LoginError: If user not found
        """
        result = await db.execute(
            select(User).where(
                and_(
                    User.email == login_init_request.email,
                    User.is_active == True,
                )
            )
        )
        user = result.scalar_one_or_none()

        if not user:
            raise LoginError("User not found")

        # Verify customer_number matches
        result = await db.execute(
            select(Tenant).where(Tenant.customer_id == user.customer_id)
        )
        tenant = result.scalar_one()

        if tenant.customer_number != login_init_request.customer_number:
            raise LoginError("Invalid tenant")

        # Fetch user's Argon2id parameters for HMAC key derivation
        result = await db.execute(
            select(UserKey).where(UserKey.user_id == user.user_id)
        )
        user_key = result.scalar_one()

        # Generate challenge nonce and store it
        nonce_store = get_nonce_store()
        challenge_nonce_hex = nonce_store.create_nonce(
            user.email, tenant.customer_number
        )
        challenge_nonce_b64 = base64.b64encode(
            bytes.fromhex(challenge_nonce_hex)
        ).decode("utf-8")

        return (
            challenge_nonce_b64,
            user_key.argon2_salt_b,
            user_key.argon2_time_cost_b,
            user_key.argon2_memory_cost_b,
            user_key.argon2_parallelism_b,
        )

    @staticmethod
    async def login_verify(
        db: AsyncSession,
        login_verify_request: LoginVerifyRequest,
    ) -> tuple[str, User]:
        """
        Step 2 of SCRAM login: Verify client_proof and issue JWT.

        Verification (server-side, never seeing hmac_key):
        1. client_signature = HMAC(stored_key, challenge_nonce)
        2. recovered_hmac_key = client_proof XOR client_signature
        3. valid if SHA256(recovered_hmac_key) == stored_key

        Args:
                db: Database session
                login_verify_request: Email, customer_number, client_proof

        Returns:
                (access_token, user)

        Raises:
                LoginError: If verification fails
        """
        result = await db.execute(
            select(User).where(
                and_(
                    User.email == login_verify_request.email,
                    User.is_active == True,
                )
            )
        )
        user = result.scalar_one_or_none()

        if not user:
            raise LoginError("Invalid credentials")

        # Verify customer_number
        result = await db.execute(
            select(Tenant).where(Tenant.customer_id == user.customer_id)
        )
        tenant = result.scalar_one()

        if tenant.customer_number != login_verify_request.customer_number:
            raise LoginError("Invalid credentials")

        # Fetch user's stored_key
        result = await db.execute(
            select(UserKey).where(UserKey.user_id == user.user_id)
        )
        user_key = result.scalar_one()

        nonce_store = get_nonce_store()
        try:
            challenge_nonce = base64.b64decode(login_verify_request.challenge_nonce)
        except Exception:
            raise LoginError("Invalid challenge encoding")

        challenge_nonce_hex = challenge_nonce.hex()
        identifier = nonce_store.get_identifier(challenge_nonce_hex)
        if identifier != f"{user.email}@{tenant.customer_number}":
            raise LoginError("Invalid credentials")

        if not nonce_store.is_valid_and_consume(challenge_nonce_hex):
            raise LoginError("Invalid credentials")

        # Verify SCRAM proof
        try:
            stored_key_bytes = base64.b64decode(user_key.stored_key, validate=True)
            client_proof = base64.b64decode(
                login_verify_request.client_proof, validate=True
            )
        except Exception as exc:
            raise LoginError("Invalid proof encoding") from exc
        proof_result = verify_client_proof(
            stored_key=stored_key_bytes,
            challenge_nonce=challenge_nonce,
            client_proof=client_proof,
        )

        if not proof_result.valid:
            raise LoginError("Invalid credentials")

        # Issue JWT token
        access_token = AuthService._create_access_token(user)

        return access_token, user

    @staticmethod
    async def get_user_crypto_material(
        db: AsyncSession,
        user_id: int,
    ) -> tuple[UserKey, CustomerKeySlot]:
        """Return only opaque key material for the authenticated user."""
        result = await db.execute(
            select(UserKey, CustomerKeySlot)
            .join(CustomerKeySlot, CustomerKeySlot.user_id == UserKey.user_id)
            .where(
                and_(
                    UserKey.user_id == user_id,
                    UserKey.is_active == True,
                )
            )
        )
        material = result.one_or_none()
        if material is None:
            raise LoginError("Cryptographic material not found")
        return material

    @staticmethod
    def _create_access_token(
        user: User,
        expires_delta: timedelta = None,
    ) -> str:
        """
        Create a JWT access token for the user.

        Args:
                user: User object
                expires_delta: Custom expiration time. Defaults to 24 hours.

        Returns:
                Encoded JWT token string
        """
        if expires_delta is None:
            expires_delta = timedelta(hours=24)

        now = datetime.now(timezone.utc)
        expire = now + expires_delta

        payload = {
            "user_id": user.user_id,
            "username": user.username,
            "email": user.email,
            "customer_id": user.customer_id,
            "iat": int(now.timestamp()),
            "exp": int(expire.timestamp()),
        }

        try:
            token = jwt.encode(
                payload,
                settings.jwt_secret,
                algorithm=settings.jwt_algorithm,
            )
            return token
        except Exception as e:
            raise LoginError(f"Failed to create token: {str(e)}")
