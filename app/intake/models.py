from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class IntakeKey(Base):
    """
    Public intake key for anonymous self-documentation.
    """

    __tablename__ = "intake_keys"

    intake_key_id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.customer_id"), nullable=False)
    label = Column(String(255), nullable=False)
    public_key = Column(String(255), nullable=False)
    encrypted_private_key = Column(String, nullable=False)
    created_by = Column(Integer, ForeignKey("users.User_ID"), nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    creator = relationship("User")


class PendingIntake(Base):
    """
    Sealed payload submitted anonymously and later claimed by staff.
    """

    __tablename__ = "pending_intakes"

    pending_intake_id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.customer_id"), nullable=False)
    intake_key_id = Column(
        Integer, ForeignKey("intake_keys.intake_key_id"), nullable=False
    )
    sealed_payload = Column(String, nullable=False)
    status = Column(String(32), nullable=False, default="pending")
    claimed_by = Column(Integer, ForeignKey("users.User_ID"), nullable=True)
    resulting_patient_id = Column(Integer, ForeignKey("patient.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    intake_key = relationship("IntakeKey")
    claimer = relationship("User")
