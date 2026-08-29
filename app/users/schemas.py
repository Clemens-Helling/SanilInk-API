from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    """
    User registration payload (from client).
    Password NEVER sent to server — it stays on client and is used for key derivation.

    Instead, client sends:
    - X25519 public key (for GEK encryption)
    - Encrypted private key (client-encrypted with password-derived key)
    - Argon2id parameters (Salt A, Salt B, time/memory/parallelism)
    - stored_key = SHA256(hmac_key) (for SCRAM proof verification)
    """
    username: str = Field(..., min_length=3, max_length=255)
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=255)
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    permission: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    customer_id: int
    username: str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    permission: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserKeyCreate(BaseModel):
    """
    Cryptographic key material sent by client during registration.
    Server stores all of this but never decrypts or derives secrets from it.
    """
    # X25519 public key (Base64-encoded, 44 bytes typically)
    public_key: str = Field(..., min_length=40, max_length=255)

    # SecretBox(key_encryption_key).encrypt(private_key) - Base64-encoded
    encrypted_private_key: str = Field(..., min_length=100)

    # Argon2id parameters for key_encryption_key derivation (Salt A, Label: "key-enc")
    argon2_salt_a: str = Field(..., min_length=20)  # Base64-encoded 16 bytes
    argon2_time_cost_a: int = Field(default=3, ge=1)
    argon2_memory_cost_a: int = Field(default=65536, ge=8192)
    argon2_parallelism_a: int = Field(default=4, ge=1)

    # SHA256(hmac_key) for SCRAM login proof (Server stores this, not hmac_key)
    stored_key: str = Field(..., min_length=40)  # Base64-encoded 32 bytes

    # Argon2id parameters for hmac_key derivation (Salt B, Label: "hmac") - MUST differ from Salt A
    argon2_salt_b: str = Field(..., min_length=20)  # Base64-encoded 16 bytes
    argon2_time_cost_b: int = Field(default=3, ge=1)
    argon2_memory_cost_b: int = Field(default=65536, ge=8192)
    argon2_parallelism_b: int = Field(default=4, ge=1)


class UserKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key_id: int
    user_id: int
    public_key: str
    created_at: datetime
    is_active: bool


class CustomerKeySlotCreate(BaseModel):
    """
    GEK encryption slot sent by client during registration.

    Client generates ephemeral keypair and encrypts GEK under user's public_key.
    Only first user in tenant generates the GEK; subsequent users get it encrypted in their slot.
    """
    ephemeral_public_key: str = Field(..., min_length=40, max_length=255)
    encrypted_gek: str = Field(..., min_length=100)


class CustomerKeySlotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slot_id: int
    customer_id: int
    user_id: int
    ephemeral_public_key: str
    created_at: datetime