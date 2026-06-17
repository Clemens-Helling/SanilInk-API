import uuid

from pydantic import BaseModel, ConfigDict
from fastapi_users import schemas


class AuthUserRead(schemas.BaseUser[uuid.UUID]):
    username: str
    first_name: str | None = None
    last_name: str | None = None


class AuthUserCreate(schemas.BaseUserCreate):
    email: str | None = None
    password: str
    username: str | None = None
    first_name: str
    last_name: str
    permission: str | None = None


class AuthUserUpdate(schemas.BaseUserUpdate):
    first_name: str | None = None
    last_name: str | None = None
    permission: str | None = None


class TeacherCreate(BaseModel):
    first_name: str
    last_name: str
    house: str


class TeacherRead(BaseModel):
    teacher_id: int
    first_name: str
    last_name: str
    house: str

    model_config = ConfigDict(from_attributes=True)
