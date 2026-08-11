from sqlalchemy import Column, Integer, String
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
