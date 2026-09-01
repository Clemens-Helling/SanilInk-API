from datetime import datetime

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)


class InviteCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    email: EmailStr
    proposed_role: str | None = Field(
        default=None,
        validation_alias=AliasChoices("proposed_role", "proposedRole"),
        description="Vorschlag, keine endgültige Zuweisung — hängt von der "
        "offenen Rollen-Modellierung ab (siehe crypto-flow.md Abschnitt 10).",
    )
    expires_in_days: int = Field(
        default=7,
        ge=1,
        le=30,
        validation_alias=AliasChoices("expires_in_days", "expiresInDays"),
    )


class InviteCreateResponse(BaseModel):
    """
    invite_token wird hier EINMALIG zurückgegeben — der Server persistiert
    nur den Hash. Wer diese Response nicht speichert/versendet, kann den
    Token nicht rekonstruieren.
    """

    invite_token: str
    email: EmailStr
    expires_at: datetime


class PendingRegistrationOut(BaseModel):
    """Für Listen-/Management-Ansichten — enthält NIE invite_token_hash."""

    model_config = ConfigDict(from_attributes=True)

    registration_id: int
    email: EmailStr
    proposed_role: str | None
    status: str
    invited_by: int
    created_at: datetime
    expires_at: datetime
    registered_at: datetime | None
    granted_at: datetime | None
    revoked_at: datetime | None


class InviteListResponse(BaseModel):
    invites: list[PendingRegistrationOut]


class InviteCheckResponse(BaseModel):
    """
    Response für den unauthentifizierten Pre-Check. Bewusst minimal — nur
    was das Frontend braucht, um das Registrierungsformular zu bauen.
    Kein customer_id, kein proposed_role (siehe Diskussion zu PII/Leak-Risiko).
    """

    email: EmailStr
    customer_name: str
    expires_at: datetime


class InviteRegisterRequest(BaseModel):
    """
    Alles hier ist bereits client-seitig verschlüsselt/abgeleitet
    (siehe crypto-flow.md Abschnitt 2, Schritte 1-6).
    Passwort, private_key, key_encryption_key, hmac_key verlassen NIE den Client.
    """

    username: str | None = None

    public_key: str = Field(..., description="Base64-kodierter X25519 Public Key")
    encrypted_private_key: str = Field(
        ..., description="Base64, SecretBox-Ciphertext inkl. Nonce"
    )

    # Argon2id-Parameter Ableitung #1 (key_encryption_key)
    argon2_salt_a: str
    argon2_time_cost_a: int = Field(..., gt=0)
    argon2_memory_cost_a: int = Field(..., gt=0)
    argon2_parallelism_a: int = Field(..., gt=0)

    # Argon2id-Parameter Ableitung #2 (hmac_key) + Login-Proof-Grundlage
    stored_key: str = Field(..., description="SHA256(hmac_key), hex-kodiert")
    argon2_salt_b: str
    argon2_time_cost_b: int = Field(..., gt=0)
    argon2_memory_cost_b: int = Field(..., gt=0)
    argon2_parallelism_b: int = Field(..., gt=0)

    @field_validator(
        "public_key",
        "encrypted_private_key",
        "argon2_salt_a",
        "argon2_salt_b",
        "stored_key",
    )
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Feld darf nicht leer sein.")
        return v


class InviteRegisterResponse(BaseModel):
    user_id: int
    status: str  # "awaiting_key_grant"
    message: str = (
        "Registrierung abgeschlossen. Warte auf Freigabe durch ein Tenant-Mitglied."
    )


class PendingGrantOut(BaseModel):
    """Eintrag in der Key-Grant-Inbox — braucht public_key des Empfängers."""

    model_config = ConfigDict(from_attributes=True)

    registration_id: int
    email: EmailStr
    user_id: int
    public_key: str  # aus dem verknüpften UserKey-Eintrag
    registered_at: datetime


class PendingGrantListResponse(BaseModel):
    pending_grants: list[PendingGrantOut]


class InviteGrantRequest(BaseModel):
    """
    ephemeral_public_key + encrypted_gek sind das Ergebnis von
    Box(ephemeral_private_key, new_user.public_key).encrypt(GEK) — komplett
    client-seitig berechnet, GEK selbst verlässt nie den Client.
    """

    model_config = ConfigDict(populate_by_name=True)

    ephemeral_public_key: str = Field(
        ...,
        description="Base64",
        validation_alias=AliasChoices("ephemeral_public_key", "ephemeralPublicKey"),
    )
    encrypted_gek: str = Field(
        ...,
        description="Base64, inkl. Nonce",
        validation_alias=AliasChoices("encrypted_gek", "encryptedGek"),
    )

    @field_validator("ephemeral_public_key", "encrypted_gek")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Feld darf nicht leer sein.")
        return v


class InviteGrantResponse(BaseModel):
    registration_id: int
    status: str  # "active"
    slot_id: int
