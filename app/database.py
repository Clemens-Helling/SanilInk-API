from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "mysql+asyncmy://root:Flecki2022%23@localhost/sani_link_api"

# Async Engine
engine = create_async_engine(DATABASE_URL, echo=True)

# Async Session
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()


# Dependency für FastAPI
async def get_session():
    async with AsyncSessionLocal() as session:
        yield session
