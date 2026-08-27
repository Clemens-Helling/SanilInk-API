from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_token_payload
from app.auth.schemas import (
    RegisterRequest,
    RegisterResponse,
    LoginInitRequest,
    LoginInitResponse,
    LoginVerifyRequest,
    LoginVerifyResponse,
    UserCryptoMaterialResponse,
)
from app.auth.service import AuthService, RegistrationError, LoginError


router = APIRouter()


@router.post(
    "/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED
)
async def register(
    register_request: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> RegisterResponse:
    try:
        user, _user_key, _key_slot = await AuthService.register(db, register_request)
        return RegisterResponse(
            user_id=user.user_id,
            username=user.username,
            email=user.email,
            customer_id=user.customer_id,
            message="Registration successful. User created with encrypted cryptographic keys.",
        )
    except RegistrationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/login/init", response_model=LoginInitResponse)
async def login_init(
    login_init_request: LoginInitRequest,
    db: AsyncSession = Depends(get_db),
) -> LoginInitResponse:
    try:
        challenge_nonce_b64, argon2_salt_b, time_cost, memory_cost, parallelism = (
            await AuthService.login_init(db, login_init_request)
        )
        return LoginInitResponse(
            challenge_nonce=challenge_nonce_b64,
            argon2_salt_b=argon2_salt_b,
            argon2_time_cost_b=time_cost,
            argon2_memory_cost_b=memory_cost,
            argon2_parallelism_b=parallelism,
        )
    except LoginError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )


@router.post("/login/verify", response_model=LoginVerifyResponse)
async def login_verify(
    login_verify_request: LoginVerifyRequest,
    db: AsyncSession = Depends(get_db),
) -> LoginVerifyResponse:
    try:
        access_token, user = await AuthService.login_verify(db, login_verify_request)
        return LoginVerifyResponse(
            access_token=access_token,
            token_type="bearer",
            user_id=user.user_id,
            username=user.username,
            message="Login successful. GEK decryption happens on client.",
        )
    except LoginError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )


@router.get("/me/keys", response_model=UserCryptoMaterialResponse)
async def get_my_crypto_material(
    payload: dict = Depends(get_current_token_payload),
    db: AsyncSession = Depends(get_db),
) -> UserCryptoMaterialResponse:
    try:
        user_key, key_slot = await AuthService.get_user_crypto_material(
            db,
            payload["user_id"],
        )
    except LoginError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Key material not found"
        )

    return UserCryptoMaterialResponse(
        user_id=user_key.user_id,
        public_key=user_key.public_key,
        encrypted_private_key=user_key.encrypted_private_key,
        argon2_salt_a=user_key.argon2_salt_a,
        argon2_time_cost_a=user_key.argon2_time_cost_a,
        argon2_memory_cost_a=user_key.argon2_memory_cost_a,
        argon2_parallelism_a=user_key.argon2_parallelism_a,
        ephemeral_public_key=key_slot.ephemeral_public_key,
        encrypted_gek=key_slot.encrypted_gek,
    )
