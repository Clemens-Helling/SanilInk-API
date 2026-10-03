from sqlalchemy import (
    CheckConstraint,
    Column,
    Index,
    Integer,
    LargeBinary,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship
from app.aid_kits.models import FirstAidKit
from app.core.database import Base


class IntakeKey(Base):
    """
    Public intake key for anonymous self-documentation.
    """

    __tablename__ = "intake_keys"

    intake_key_id = Column(Integer, primary_key=True)
    kit_id = Column(Integer, ForeignKey("first_aid_kits.kit_id"), nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.customer_id"), nullable=False)
    label = Column(String(255), nullable=False)
    public_key = Column(String(255), nullable=False)
    encrypted_private_key = Column(String, nullable=False)
    created_by = Column(Integer, ForeignKey("users.User_ID"), nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    creator = relationship("User")
    kit = relationship("FirstAidKit", back_populates="intake_keys")


class PendingIntake(Base):
    """
    Sealed payload submitted anonymously and later claimed by staff.
    """

    __tablename__ = "pending_intakes"

    pending_intake_id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.customer_id"), nullable=False)
    intake_key_id = Column(
        Integer, ForeignKey("intake_keys.intake_key_id"), nullable=False, index=True
    )
    sealed_payload = Column(LargeBinary, nullable=False)
    status = Column(
        String(32), nullable=False, default="pending", server_default="pending"
    )
    claimed_by = Column(Integer, ForeignKey("users.User_ID"), nullable=True)
    claimed_at = Column(DateTime(timezone=True), nullable=True)
    resulting_patient_id = Column(
        Integer, ForeignKey("patient.id", ondelete="SET NULL"), nullable=True
    )
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    intake_key = relationship("IntakeKey")
    claimer = relationship("User")

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'claimed', 'rejected', 'expired')",
            name="ck_pending_intakes_status",
        ),
        CheckConstraint(
            "status <> 'claimed' OR (claimed_by IS NOT NULL "
            "AND claimed_at IS NOT NULL)",
            name="ck_pending_intakes_claimed_fields",
        ),
        CheckConstraint(
            "octet_length(sealed_payload) <= 65536",
            name="ck_pending_intakes_payload_size",
        ),
        Index("ix_pending_intakes_inbox", "customer_id", "status"),
        UniqueConstraint(
            "customer_id",
            "pending_intake_id",
            name="uq_pending_intakes_customer_intake",
        ),
    )
