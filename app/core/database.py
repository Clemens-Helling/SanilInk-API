from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings
from app.core.security import get_current_token_payload


class Base(DeclarativeBase):
    pass


engine = create_async_engine(settings.database_url, echo=False)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with async_session_factory() as session:
        yield session


async def set_tenant_context(db: AsyncSession, customer_id: int) -> None:
    await db.execute(
        text("SELECT set_config('app.current_customer_id', :customer_id, true)"),
        {"customer_id": str(customer_id)},
    )


async def get_tenant_db(
    payload: dict = Depends(get_current_token_payload),
    db: AsyncSession = Depends(get_db),
) -> AsyncSession:
    await set_tenant_context(db, payload["customer_id"])
    return db
