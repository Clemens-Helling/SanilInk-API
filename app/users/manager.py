import uuid

from fastapi import Depends, Request
from fastapi_users import BaseUserManager, UUIDIDMixin
from sqlalchemy import select

from app.users.db import get_user_db
from app.users.models import AuthUser

SECRET = "CHANGE_ME_IN_PRODUCTION"


class UserManager(UUIDIDMixin, BaseUserManager[AuthUser, uuid.UUID]):
    reset_password_token_secret = SECRET
    verification_token_secret = SECRET

    def _build_email(self, username: str) -> str:
        return f"{username}@sanilink.com"

    async def _build_unique_username(self, first_name: str, last_name: str) -> str:
        base_username = f"{first_name[:3]}{last_name[:3]}".lower()
        base_username = "".join(
            character for character in base_username if character.isalnum()
        )
        if not base_username:
            base_username = "user"

        candidate = base_username
        suffix = 1

        while True:
            result = await self.user_db.session.execute(
                select(AuthUser).where(AuthUser.username == candidate)
            )
            existing_user = result.scalar_one_or_none()
            if existing_user is None:
                return candidate
            candidate = f"{base_username}{suffix}"
            suffix += 1

    async def create(
        self, user_create, safe: bool = False, request: Request | None = None
    ):
        username = await self._build_unique_username(
            user_create.first_name,
            user_create.last_name,
        )
        email = user_create.email or self._build_email(username)
        user_create = user_create.model_copy(
            update={"username": username, "email": email}
        )
        return await super().create(user_create, safe=safe, request=request)

    async def update(
        self, user, user_update, safe: bool = False, request: Request | None = None
    ):
        updated_user = await super().update(
            user, user_update, safe=safe, request=request
        )

        if user_update.first_name is not None or user_update.last_name is not None:
            first_name = (
                user_update.first_name
                if user_update.first_name is not None
                else updated_user.first_name or ""
            )
            last_name = (
                user_update.last_name
                if user_update.last_name is not None
                else updated_user.last_name or ""
            )
            if first_name and last_name:
                updated_user.username = await self._build_unique_username(
                    first_name, last_name
                )
                await self.user_db.update(
                    updated_user, {"username": updated_user.username}
                )

        return updated_user

    async def authenticate(self, credentials) -> AuthUser | None:
        result = await self.user_db.session.execute(
            select(AuthUser).where(AuthUser.username == credentials.username)
        )
        user = result.scalar_one_or_none()

        if user is None:
            user = await self.user_db.get_by_email(credentials.username)

        if user is None:
            # Keep timing comparable even when user does not exist.
            self.password_helper.hash(credentials.password)
            return None

        verified, updated_password_hash = self.password_helper.verify_and_update(
            credentials.password, user.hashed_password
        )
        if not verified:
            return None

        if updated_password_hash is not None:
            await self.user_db.update(user, {"hashed_password": updated_password_hash})

        return user

    async def on_after_register(self, user: AuthUser, request: Request | None = None):
        print(f"User {user.id} has registered.")


async def get_user_manager(user_db=Depends(get_user_db)):
    yield UserManager(user_db)
