from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AidKitCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    building_id: int = Field(gt=0)
    label: str = Field(min_length=1, max_length=100)
    location_detail: str | None = Field(default=None, max_length=200)
    is_active: bool = True


class AidKitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kit_id: int
    building_id: int
    label: str
    location_detail: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
