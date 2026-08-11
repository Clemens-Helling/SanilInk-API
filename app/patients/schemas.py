from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class PatientCreate(BaseModel):
	"""
	Patient creation payload.
	Sensitive fields MUST be encrypted client-side with SecretBox(GEK).
	Server receives only Base64-encoded ciphertexts.
	"""
	# Base64-encoded SecretBox ciphertexts (XSalsa20-Poly1305, includes Nonce)
	encrypted_real_name: str = Field(..., min_length=50)
	encrypted_real_last_name: str = Field(..., min_length=50)
	encrypted_birth_day: str = Field(..., min_length=50)
	
	# Optional: pseudonym (can be plaintext or also encrypted)
	pseudonym: Optional[str] = None


class PatientUpdate(BaseModel):
	encrypted_real_name: Optional[str] = None
	encrypted_real_last_name: Optional[str] = None
	encrypted_birth_day: Optional[str] = None
	pseudonym: Optional[str] = None


class PatientResponse(BaseModel):
	"""
	Patient response - returns encrypted fields as-is.
	Client decrypts on read using its local GEK.
	"""
	patient_id: int
	customer_id: int
	encrypted_real_name: str
	encrypted_real_last_name: str
	encrypted_birth_day: str
	pseudonym: Optional[str]
	is_active: bool
	created_at: datetime
	updated_at: datetime

	class Config:
		from_attributes = True


class PatientDecrypted(BaseModel):
	"""
	Client-side model: plaintext patient data after decryption.
	This model is NEVER returned from API - only used for client-side processing.
	"""
	patient_id: int
	real_name: str
	real_last_name: str
	birth_day: str
	pseudonym: Optional[str]


class ProtocolCreate(BaseModel):
	patient_id: int
	alert_id: Optional[int] = None
	pulse: Optional[int] = None
	spo2: Optional[int] = None
	blood_pressure: Optional[str] = None
	temperature: Optional[int] = None
	blood_sugar: Optional[int] = None
	pain: Optional[str] = None
	measures: Optional[str] = None
	status: Optional[str] = None


class ProtocolResponse(BaseModel):
	protokoll_id: int
	customer_id: int
	patient_id: Optional[int]
	alert_id: Optional[int]
	pulse: Optional[int]
	spo2: Optional[int]
	blood_pressure: Optional[str]
	temperature: Optional[int]
	blood_sugar: Optional[int]
	pain: Optional[str]
	measures: Optional[str]
	status: Optional[str]
	operation_end: Optional[datetime]
	created_at: datetime
	updated_at: datetime

	class Config:
		from_attributes = True
