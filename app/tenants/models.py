from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class Tenant(Base):
    """
    Tenant/Customer - represents an organization.
    Serves as the isolation boundary for all data (RLS on tenant_id/customer_id).
    """

    __tablename__ = "customers"

    customer_id = Column(Integer, primary_key=True)
    customer_number = Column(String(100), unique=True, nullable=False)
    contact_person_first_name = Column(String(255))
    contact_person_last_name = Column(String(255))
    email = Column(String(100))
    phone_number = Column(String(100))


class Building(Base):
    __tablename__ = "buildings"

    building_id = Column(Integer, primary_key=True)
    customer_id = Column(
        Integer, ForeignKey("customers.customer_id"), nullable=False, index=True
    )
    building_name = Column(String(100), nullable=False)
    street = Column(String(150), nullable=False)
    house_number = Column(String(20), nullable=False)
    postal_code = Column(String(10), nullable=False)
    city = Column(String(100), nullable=False)
    country_code = Column(String(2), nullable=False, default="DE", server_default="DE")
    address_additional = Column(String(150), nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    kits = relationship("FirstAidKit", back_populates="building")

    __table_args__ = (
        # Ziel für den Composite-FK aus first_aid_kits
        UniqueConstraint(
            "customer_id", "building_id", name="uq_buildings_customer_building"
        ),
        UniqueConstraint(
            "customer_id", "building_name", name="uq_buildings_customer_name"
        ),
        CheckConstraint(
            "country_code ~ '^[A-Z]{2}$'", name="ck_buildings_country_code"
        ),
    )


class FirstAidKit(Base):
    __tablename__ = "first_aid_kits"

    kit_id = Column(Integer, primary_key=True)
    customer_id = Column(
        Integer, ForeignKey("customers.customer_id"), nullable=False, index=True
    )
    building_id = Column(Integer, nullable=False, index=True)
    label = Column(String(100), nullable=False)
    location_detail = Column(String(200), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    building = relationship("Building", back_populates="kits")
    intake_keys = relationship("IntakeKey", back_populates="kit")

    __table_args__ = (
        ForeignKeyConstraint(
            ["customer_id", "building_id"],
            ["buildings.customer_id", "buildings.building_id"],
            name="fk_kits_customer_building",
        ),
        # Ziel für den Composite-FK aus intake_keys
        UniqueConstraint("customer_id", "kit_id", name="uq_kits_customer_kit"),
        UniqueConstraint("customer_id", "label", name="uq_kits_customer_label"),
    )
