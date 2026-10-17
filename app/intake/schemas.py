from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class IntakeKeyCreate(BaseModel):
    kit_id: int = Field(..., gt=0)
    label: str = Field(..., min_length=2, max_length=255)
    public_key: str = Field(..., min_length=40, max_length=255)
    encrypted_private_key: str = Field(..., min_length=100)


class IntakeKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    intake_key_id: int
    customer_id: int
    kit_id: int
    label: str
    public_key: str
    created_by: int
    revoked_at: Optional[datetime] = None
    created_at: datetime


class IntakeSubmitRequest(BaseModel):
    sealed_payload: str = Field(..., min_length=50, max_length=87384)


class IntakeSubmitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pending_intake_id: int
    status: str


class PendingIntakeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pending_intake_id: int
    intake_key_id: int
    sealed_payload: str
    public_key: str
    encrypted_private_key: str
    kit_label: str
    kit_location_detail: Optional[str] = None
    status: str
    created_at: datetime
    claimed_by: Optional[int] = None
    resulting_patient_id: Optional[int] = None
