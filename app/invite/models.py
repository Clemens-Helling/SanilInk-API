import enum
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
    CheckConstraint,
)
from sqlalchemy.orm import relationship
from app.core.database import Base


class RegistrationStatus(str, enum.Enum):
    """Lifecycle-Status eines Invites (siehe crypto-flow.md Abschnitt 7)."""

    INVITED = "invited"  # Phase 1: Link verschickt
    AWAITING_KEY_GRANT = (
        "awaiting_key_grant"  # Phase 2: registriert, wartet auf GEK-Grant
    )
    ACTIVE = "active"  # Phase 3: Key-Slot angelegt, einsatzbereit
    EXPIRED = "expired"  # expires_at überschritten, nie registriert
    REVOKED = "revoked"  # von Admin zurückgezogen (vor Registrierung)


class PendingRegistration(Base):
    """
    Verwaltet den dreiphasigen Invite-Flow für neue Kunden-/Tenant-Mitglieder.

    Phase 1 (invited):            invite_token_hash gesetzt, user_id NULL
    Phase 2 (awaiting_key_grant): user_id gesetzt (users-Eintrag existiert bereits,
                                   hat aber noch keinen Slot in customer_key_slots)
    Phase 3 (active):             granted_by/granted_at gesetzt, Key-Slot angelegt
    """

    __tablename__ = "pending_registrations"

    registration_id = Column(Integer, primary_key=True)

    customer_id = Column(Integer, ForeignKey("customers.customer_id"), nullable=False)

    email = Column(String(255), nullable=False)

    # SHA256-Hash des Invite-Tokens (64 hex chars) — das Token selbst wird
    # serverseitig NIE persistiert, nur der Hash (analog stored_key).
    invite_token_hash = Column(String(64), nullable=False, unique=True)

    # Vorschlag, keine endgültige Zuweisung — abhängig von der offenen
    # Rollen-Modellierung, siehe crypto-flow.md Abschnitt 10.
    proposed_role = Column(String(255), nullable=True)

    status = Column(
        Enum(RegistrationStatus, name="registration_status", native_enum=True),
        nullable=False,
        default=RegistrationStatus.INVITED,
        server_default=RegistrationStatus.INVITED.value,
    )

    invited_by = Column(Integer, ForeignKey("users.User_ID"), nullable=False)

    # NULL bis Phase 2 abgeschlossen ist. Verknüpft den Invite mit dem
    # tatsächlichen users-Eintrag, damit Phase 3 dessen public_key findet
    # (robuster als erneutes Matching über email).
    user_id = Column(Integer, ForeignKey("users.User_ID"), nullable=True)

    # NULL bis Phase 3 abgeschlossen ist.
    granted_by = Column(Integer, ForeignKey("users.User_ID"), nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=False)
    registered_at = Column(DateTime, nullable=True)
    granted_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)

    # Mehrere FKs zeigen auf users -> foreign_keys explizit angeben, sonst
    # kann SQLAlchemy die relationship nicht eindeutig auflösen.
    customer = relationship("Tenant", foreign_keys=[customer_id])
    invited_by_user = relationship(
        "User", foreign_keys=[invited_by], back_populates="invites_sent"
    )
    registered_user = relationship(
        "User", foreign_keys=[user_id], back_populates="own_registration"
    )
    granted_by_user = relationship(
        "User", foreign_keys=[granted_by], back_populates="grants_given"
    )

    __table_args__ = (
        # Verhindert mehrere gleichzeitig offene Invites für dieselbe E-Mail
        # innerhalb desselben Kunden.
        Index(
            "uq_pending_registrations_active_email",
            "customer_id",
            "email",
            unique=True,
            postgresql_where=(
                status.in_(
                    [RegistrationStatus.INVITED, RegistrationStatus.AWAITING_KEY_GRANT]
                )
            ),
        ),
        # Deckt die Key-Grant-Inbox-Query beim Login ab (analog pending_intakes).
        Index(
            "ix_pending_registrations_awaiting_grant",
            "customer_id",
            "status",
            postgresql_where=(status == RegistrationStatus.AWAITING_KEY_GRANT),
        ),
        # Konsistenz-Checks auf DB-Ebene, unabhängig von Anwendungslogik-Bugs:
        CheckConstraint(
            "(status = 'invited' AND user_id IS NULL) OR (status != 'invited')",
            name="ck_invited_has_no_user",
        ),
        CheckConstraint(
            "(status = 'active' AND granted_by IS NOT NULL AND granted_at IS NOT NULL) "
            "OR (status != 'active')",
            name="ck_active_requires_grant",
        ),
    )
