import pytest
from datetime import datetime, timezone
from httpx import AsyncClient
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.models import Event, EventSymbol, EventType
from app.settings import settings


@pytest.fixture(name="override_db")
async def override_db_fixture():
    # connect to the real postgres database defined in settings
    from app.settings import settings
    engine = create_async_engine(str(settings.DATABASE_URL), echo=False)
    # ensure clean state
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
    AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async def get_test_db():
        async with AsyncSessionLocal() as session:
            yield session

    from app.settings.db import get_db
    app.dependency_overrides[get_db] = get_test_db
    yield AsyncSessionLocal
    from app.settings.db import get_db
    app.dependency_overrides.pop(get_db, None)


class DummyRedis:
    def __init__(self):
        self.store = {}

    def get(self, key):
        return self.store.get(key)

    def set(self, key, val):
        self.store[key] = val

    def ping(self):
        return True

    def flushdb(self):
        self.store.clear()


@pytest.fixture(autouse=True)
def override_redis(monkeypatch):
    from app.settings import db
    dummy = DummyRedis()
    monkeypatch.setattr(db, "redis_client", dummy)
    return dummy


def add_event(session: AsyncSession) -> str:
    # helper to create a single event and return its id
    async def _inner():
        sym = EventSymbol(name="ABC")
        typ = EventType(name="earnings")
        session.add_all([sym, typ])
        await session.commit()
        await session.refresh(sym)
        await session.refresh(typ)
        evt = Event(
            event_id="eid",
            symbol=sym.id,
            event_type=typ.id,
            event_date=datetime.now(timezone.utc),
            title="T",
            details={},
            event_metadata={},
            description=None,
            exchange=None,
        )
        session.add(evt)
        await session.commit()
        await session.refresh(evt)
        return str(evt.id)
    return _inner


@pytest.mark.asyncio
async def test_get_events_endpoint(override_db):
    AsyncSessionLocal = override_db
    async with AsyncSessionLocal() as session:
        # add some data
        get_id = add_event(session)
        event_id = await get_id()
    from httpx import ASGITransport
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # include trailing slash to avoid 307 redirect
        r = await client.get(f"{settings.API_V1_STR}/events/")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1

        # test caching header on single event
        r2 = await client.get(f"{settings.API_V1_STR}/events/{event_id}")
        assert r2.status_code == 200
        assert r2.headers.get("X-Cache") in ("HIT", "MISS")

        # second call should be hit
        r3 = await client.get(f"{settings.API_V1_STR}/events/{event_id}")
        assert r3.headers.get("X-Cache") == "HIT"


@pytest.mark.asyncio
async def test_sync_endpoint(override_db, override_redis, monkeypatch):
    # patch providers same as in service tests
    event_template = {
        "event_id": "evt1",
        "symbol": "TEST",
        "event_type": "earnings",
        "event_date": "2026-03-15T00:00:00Z",
        "title": "Test",
        "details": {},
        "metadata": {},
    }

    class FakeProv:
        async def fetch_events(self, symbols, days_ahead=30):
            return [event_template.copy()]

    monkeypatch.setattr("app.api.routes.events.service.ProviderA", lambda: FakeProv())
    monkeypatch.setattr("app.api.routes.events.service.ProviderB", lambda: FakeProv())

    # override_db fixture returns AsyncSessionLocal
    AsyncSessionLocal = override_db

    from httpx import ASGITransport
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {"symbols": ["TEST"], "force": False}
        r = await client.post(f"{settings.API_V1_STR}/events/sync", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "completed"
        assert data["events_created"] == 1


@pytest.mark.asyncio
async def test_health_endpoint():
    from httpx import ASGITransport
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get(f"{settings.API_V1_STR}/health")
        assert r.status_code == 200
        data = r.json()
        assert "redis" in data and "db" in data
