from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.users.models import User
from app.users.schemas import UserCreate, UserUpdate


class UserServiceError(Exception):
    """Fehler bei User-CRUD-Operationen."""


class UserService:
    @staticmethod
    async def list_users(db: AsyncSession, customer_id: int) -> list[User]:
        result = await db.execute(
            select(User).options(selectinload(User.customer_key_slots)).where(User.customer_id == customer_id).order_by(User.user_id)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_user(db: AsyncSession, user_id: int, customer_id: int) -> User:
        result = await db.execute(
            select(User).options(selectinload(User.customer_key_slots)).where(
                User.user_id == user_id,
                User.customer_id == customer_id,
            )
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise UserServiceError("User not found")
        return user

    @staticmethod
    async def create_user(
        db: AsyncSession, user_create: UserCreate, customer_id: int
    ) -> User:
        user = User(
            customer_id=customer_id,
            username=user_create.username,
            email=str(user_create.email),
            first_name=user_create.first_name,
            last_name=user_create.last_name,
            is_active=True,
        )
        db.add(user)
        try:
            await db.commit()
            await db.refresh(user)
        except IntegrityError as exc:
            await db.rollback()
            raise UserServiceError("Username or email already exists") from exc
        return user

    @staticmethod
    async def update_user(
        db: AsyncSession,
        user_id: int,
        user_update: UserUpdate,
        customer_id: int,
    ) -> User:
        user = await UserService.get_user(db, user_id, customer_id)
        for field, value in user_update.model_dump(exclude_unset=True).items():
            if field == "email" and value is not None:
                value = str(value)
            setattr(user, field, value)
        try:
            await db.commit()
            await db.refresh(user)
        except IntegrityError as exc:
            await db.rollback()
            raise UserServiceError("Username or email already exists") from exc
        return user

    @staticmethod
    async def delete_user(db: AsyncSession, user_id: int, customer_id: int) -> None:
        user = await UserService.get_user(db, user_id, customer_id)
        user.is_active = False
        await db.commit()
