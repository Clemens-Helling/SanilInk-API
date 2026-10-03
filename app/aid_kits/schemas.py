from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class AidKitResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    building_id: int
    label: str
    location: str
    is_active: bool
    created_at: datetime


class AidKitCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    building_id: int = Field(..., gt=0)
    label: str = Field(..., min_length=1, max_length=100)
    location: str = Field(..., min_length=1, max_length=200)
    is_active: bool = True
    created_at: datetime
