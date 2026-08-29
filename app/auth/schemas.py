from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    """
    Complete registration request with cryptographic material.
    Password is NEVER transmitted - only derived key material is sent.

    Flow:
    1. Client: generate X25519 keypair → public_key
    2. Client: encrypt private_key with password-derived key_encryption_key
    3. Client: derive stored_key = SHA256(hmac_key) for login verification
    4. Client: generate GEK (if first user in tenant) and encrypt it
    5. Client: send all of above to server
    """

    customer_number: str = Field(..., min_length=1, max_length=100)
    username: str = Field(..., min_length=3, max_length=255)
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None

    # X25519 public key (Base64, ~44 chars)
    public_key: str = Field(..., min_length=40, max_length=255)

    # SecretBox(key_encryption_key).encrypt(private_key)
    encrypted_private_key: str = Field(..., min_length=40)

    # Argon2id params for key_encryption_key (Domain Separation Salt A, Label: "key-enc")
    argon2_salt_a: str = Field(..., min_length=20)
    argon2_time_cost_a: int = Field(default=3, ge=1)
    argon2_memory_cost_a: int = Field(default=65536, ge=8192)
    argon2_parallelism_a: int = Field(default=4, ge=1)

    # SHA256(hmac_key) for SCRAM login proof
    stored_key: str = Field(..., min_length=40)

    # Argon2id params for hmac_key (Domain Separation Salt B, Label: "hmac") - MUST differ from Salt A!
    argon2_salt_b: str = Field(..., min_length=20)
    argon2_time_cost_b: int = Field(default=3, ge=1)
    argon2_memory_cost_b: int = Field(default=65536, ge=8192)
    argon2_parallelism_b: int = Field(default=4, ge=1)

    # GEK encryption slot (ephemeral public key + encrypted GEK)
    ephemeral_public_key: str = Field(..., min_length=40, max_length=255)
    encrypted_gek: str = Field(..., min_length=40)


class RegisterResponse(BaseModel):
    """Response after successful registration."""

    model_config = ConfigDict(from_attributes=True)

    user_id: int
    username: str
    email: str
    customer_id: int
    message: str = "Registration successful"


class LoginInitRequest(BaseModel):
    """
    Step 1 of SCRAM-proof login: Client requests challenge.
    Server responds with nonce + Argon2id parameters.
    """

    email: EmailStr
    customer_number: str


class LoginInitResponse(BaseModel):
    """
    Step 1 response: Server sends challenge_nonce + Argon2id parameters.
    Client will use these to derive hmac_key and compute ClientProof.
    """

    challenge_nonce: str = Field(..., min_length=40)  # Base64-encoded
    argon2_salt_b: str  # For hmac_key derivation
    argon2_time_cost_b: int
    argon2_memory_cost_b: int
    argon2_parallelism_b: int


class LoginVerifyRequest(BaseModel):
    """
    Step 2 of SCRAM-proof login: Client sends proof.

    ClientProof = hmac_key XOR HMAC(stored_key, challenge_nonce)
    Server can verify without ever seeing hmac_key:
      - ClientSignature = HMAC(stored_key, challenge_nonce)
      - recovered_hmac_key = ClientProof XOR ClientSignature
      - valid if SHA256(recovered_hmac_key) == stored_key
    """

    email: EmailStr
    customer_number: str
    challenge_nonce: str = Field(..., min_length=40)
    client_proof: str = Field(..., min_length=40)  # Base64-encoded


class LoginVerifyResponse(BaseModel):
    """Response after successful login."""

    model_config = ConfigDict(from_attributes=True)

    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str
    message: str = "Login successful"


class UserCryptoMaterialResponse(BaseModel):
    """Opaque key material the client decrypts after a successful login."""

    user_id: int
    public_key: str
    encrypted_private_key: str
    argon2_salt_a: str
    argon2_time_cost_a: int
    argon2_memory_cost_a: int
    argon2_parallelism_a: int
    ephemeral_public_key: str
    encrypted_gek: str


class UserRegistration(BaseModel):
    """Legacy model - kept for backward compatibility."""

    tenant_name: str
    username: str
    public_key: str
    encrypted_private_key: str
    argon2_salt: str
    hmac_verifier: str
    stored_key: str
    encrypted_gek_slot: str
    ephemeral_pubkey: str
