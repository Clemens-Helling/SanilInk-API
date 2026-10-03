from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class TenantCreate(BaseModel):
	customer_number: str = Field(..., min_length=1, max_length=100)
	contact_person_first_name: Optional[str] = None
	contact_person_last_name: Optional[str] = None
	email: Optional[str] = None
	phone_number: Optional[str] = None


class TenantUpdate(BaseModel):
	contact_person_first_name: Optional[str] = None
	contact_person_last_name: Optional[str] = None
	email: Optional[str] = None
	phone_number: Optional[str] = None


class TenantResponse(BaseModel):
	customer_id: int
	customer_number: str
	contact_person_first_name: Optional[str]
	contact_person_last_name: Optional[str]
	email: Optional[str]
	phone_number: Optional[str]
	created_at: datetime
	updated_at: datetime

	class Config:
		from_attributes = True


class BuildingCreate(BaseModel):
	building_name: str = Field(..., min_length=1, max_length=100)
	street: str = Field(..., min_length=1, max_length=150)
	house_number: str = Field(..., min_length=1, max_length=20)
	postal_code: str = Field(..., min_length=1, max_length=10)
	city: str = Field(..., min_length=1, max_length=100)
	country_code: str = Field(default="DE", min_length=2, max_length=2)
	address_additional: Optional[str] = Field(default=None, max_length=150)


class BuildingResponse(BuildingCreate):
	building_id: int
	customer_id: int
	created_at: datetime

	model_config = ConfigDict(from_attributes=True)
