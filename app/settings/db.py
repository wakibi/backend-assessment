from collections.abc import AsyncGenerator

import redis
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.settings import settings

# use async engine for asyncpg
engine = create_async_engine(str(settings.DATABASE_URL), echo=False)
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

redis_client = redis.from_url(settings.REDIS_URL)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
