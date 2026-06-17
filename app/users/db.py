from fastapi import Depends
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.users.models import AuthUser


async def get_user_db(session: AsyncSession = Depends(get_session)):
    yield SQLAlchemyUserDatabase(session, AuthUser)
