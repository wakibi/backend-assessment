import pytest
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker


@pytest.fixture(name="db_session")
async def db_session_fixture():
    """Provide a clean AsyncSession backed by the project's Postgres test DB.

    The fixture drops and recreates all tables before yielding a session so that
    every test starts from a blank schema.  This mirrors what the original
    in-memory SQLite fixture did but now uses the real database per latest
    suggestion.
    """
    from app.settings import settings

    engine = create_async_engine(str(settings.DATABASE_URL), echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
    AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with AsyncSessionLocal() as session:
        yield session
