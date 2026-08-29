from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, func

from app.core.database import Base


class Patient(Base):
	"""
	Legacy patient table extended with encrypted fields.
	"""
	__tablename__ = "patient"

	patient_id = Column("id", Integer, primary_key=True)
	customer_id = Column("customer", Integer, ForeignKey("customers.customer_id"), nullable=False)
	real_name = Column(String)
	real_last_name = Column(String)
	birth_day = Column(String)
	created_at = Column(DateTime)
	pseudonym = Column(String(255), unique=True)
	encrypted_real_name = Column(String)
	encrypted_real_last_name = Column(String)
	encrypted_birth_day = Column(String)
	is_active = Column(Boolean, default=True)


class Protocol(Base):
	"""
	Legacy protocol table.
	"""
	__tablename__ = "protokolle"

	protokoll_id = Column(Integer, primary_key=True)
	customer_id = Column("customer", Integer, ForeignKey("customers.customer_id"), nullable=False)
	alert_id = Column(Integer, ForeignKey("alarmierungen.alert_id"))
	pseudonym = Column(String(255), ForeignKey("patient.pseudonym"))
	teacher_id = Column("teacher_id", Integer, ForeignKey("teachers.teacher_id"))
	operation_end = Column(DateTime)
	status = Column(String(255))
	pulse = Column(Integer)
	spo2 = Column(Integer)
	blood_pressure = Column(String(255))
	temperature = Column(Integer)
	blood_sugar = Column(Integer)
	pain = Column(String(255))
	measures = Column(String)
	abhol_massnahme = Column(String(255))
	parents_notified_by = Column(String(255))
	parents_notified_at = Column(DateTime)
	hospital = Column(String(255))
	medic_id = Column(Integer)
