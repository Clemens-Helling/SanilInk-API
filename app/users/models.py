from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class User(Base):
    """
    Legacy users table extended with auth fields.
    """

    __tablename__ = "users"

    user_id = Column("User_ID", Integer, primary_key=True)
    customer_id = Column(
        "customer", Integer, ForeignKey("customers.customer_id"), nullable=False
    )
    first_name = Column("name", String(255))
    last_name = Column("last_name", String(255))
    teacher = Column(Integer)
    departement = Column(Integer)
    karten_nummer = Column(String(255))
    permission = Column(String(255))

    username = Column(String(255))
    email = Column(String(255), unique=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user_keys = relationship(
        "UserKey", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    customer_key_slots = relationship(
        "CustomerKeySlot", back_populates="user", cascade="all, delete-orphan"
    )


class UserKey(Base):
    """
    Cryptographic material for a user.
    """

    __tablename__ = "user_keys"

    key_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.User_ID"), nullable=False)
    public_key = Column(String, nullable=False)
    encrypted_private_key = Column(String, nullable=False)
    argon2_salt_a = Column("argon2_salt", String(255), nullable=False)
    argon2_time_cost_a = Column(Integer, nullable=True)
    argon2_memory_cost_a = Column(Integer, nullable=True)
    argon2_parallelism_a = Column(Integer, nullable=True)
    stored_key = Column(String(255), nullable=False)
    argon2_salt_b = Column(String(255), nullable=False)
    argon2_time_cost_b = Column(Integer, nullable=False)
    argon2_memory_cost_b = Column(Integer, nullable=False)
    argon2_parallelism_b = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    is_active = Column(Boolean, default=True)

    user = relationship("User", back_populates="user_keys")


class CustomerKeySlot(Base):
    """
    GEK slot per user and tenant.
    """

    __tablename__ = "customer_key_slots"

    slot_id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.customer_id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.User_ID"), nullable=False)
    ephemeral_public_key = Column(String(255), nullable=False)
    encrypted_gek = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="customer_key_slots")
