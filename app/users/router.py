from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_tenant_db
from app.core.security import get_current_token_payload
from app.users.schemas import UserCreate, UserResponse, UserUpdate
from app.users.service import UserService, UserServiceError


router = APIRouter()


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_create: UserCreate,
    payload: dict = Depends(get_current_token_payload),
    db: AsyncSession = Depends(get_tenant_db),
) -> UserResponse:
    try:
        return await UserService.create_user(db, user_create, payload["customer_id"])
    except UserServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc


@router.get("/", response_model=list[UserResponse])
async def list_users(
    payload: dict = Depends(get_current_token_payload),
    db: AsyncSession = Depends(get_tenant_db),
) -> list[UserResponse]:
    return await UserService.list_users(db, payload["customer_id"])


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    payload: dict = Depends(get_current_token_payload),
    db: AsyncSession = Depends(get_tenant_db),
) -> UserResponse:
    try:
        return await UserService.get_user(db, user_id, payload["customer_id"])
    except UserServiceError as exc:
        raise _not_found() from exc


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    payload: dict = Depends(get_current_token_payload),
    db: AsyncSession = Depends(get_tenant_db),
) -> UserResponse:
    try:
        return await UserService.update_user(
            db, user_id, user_update, payload["customer_id"]
        )
    except UserServiceError as exc:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if str(exc) == "User not found"
            else status.HTTP_409_CONFLICT
        )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    payload: dict = Depends(get_current_token_payload),
    db: AsyncSession = Depends(get_tenant_db),
) -> None:
    try:
        await UserService.delete_user(db, user_id, payload["customer_id"])
    except UserServiceError as exc:
        raise _not_found() from exc
