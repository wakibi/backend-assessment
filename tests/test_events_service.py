from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import SQLModel, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.models import Event, EventSymbol, EventType
from app.api.routes.events.service import EventService


@pytest.fixture(name="in_memory_session")
async def in_memory_session_fixture():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with AsyncSessionLocal() as session:
        yield session


async def seed_data(session: AsyncSession):
    """Insert a symbol, a type, and a couple of events."""
    sym = EventSymbol(name="AAPL")
    typ = EventType(name="earnings")
    session.add_all([sym, typ])
    await session.commit()
    await session.refresh(sym)
    await session.refresh(typ)

    base_date = datetime(2026, 2, 20, tzinfo=timezone.utc)
    e1 = Event(
        event_id="e1",
        symbol=sym.id,
        event_type=typ.id,
        event_date=base_date,
        title="First",
        details={},
        metadata={},
        description=None,
        exchange=1,
    )
    e2 = Event(
        event_id="e2",
        symbol=sym.id,
        event_type=typ.id,
        event_date=base_date + timedelta(days=1),
        title="Second",
        details={"foo": "bar"},
        metadata={},
        description=None,
        exchange=1,
    )
    session.add_all([e1, e2])
    await session.commit()


@pytest.mark.asyncio
async def test_get_events_basic(in_memory_session):
    session = in_memory_session
    await seed_data(session)
    result = await EventService.get_events(session)
    assert result.total == 2
    assert len(result.data) == 2
    assert result.has_more is False
    assert result.data[0].symbol == "AAPL"
    assert result.data[0].event_type == "earnings"


@pytest.mark.asyncio
async def test_get_events_pagination(in_memory_session):
    session = in_memory_session
    await seed_data(session)
    res1 = await EventService.get_events(session, limit=1, offset=0)
    assert res1.total == 2
    assert len(res1.data) == 1
    assert res1.has_more is True
    res2 = await EventService.get_events(session, limit=1, offset=1)
    assert len(res2.data) == 1
    assert res2.has_more is False


@pytest.mark.asyncio
async def test_get_events_filters(in_memory_session):
    session = in_memory_session
    await seed_data(session)
    # by symbol
    r = await EventService.get_events(session, symbols="AAPL")
    assert r.total == 2
    # by event_type
    r = await EventService.get_events(session, event_type="earnings")
    assert r.total == 2
    # by date range
    r = await EventService.get_events(
        session,
        from_date=datetime(2026, 2, 21, tzinfo=timezone.utc),
        to_date=datetime(2026, 2, 21, tzinfo=timezone.utc),
    )
    assert r.total == 1


@pytest.mark.asyncio
async def test_invalid_params(in_memory_session):
    session = in_memory_session
    await seed_data(session)
    with pytest.raises(Exception):
        await EventService.get_events(session, limit=0)
    with pytest.raises(Exception):
        await EventService.get_events(
            session,
            from_date=datetime(2026, 2, 22, tzinfo=timezone.utc),
            to_date=datetime(2026, 2, 21, tzinfo=timezone.utc),
        )


@pytest.mark.asyncio
async def test_get_event_caching(in_memory_session):
    # ensure redis is cleared or skip if unavailable
    from app.settings.db import redis_client
    try:
        redis_client.flushdb()
    except Exception:
        pytest.skip("redis not available")

    session = in_memory_session
    await seed_data(session)
    # grab an event id
    result = await session.execute(select(Event).limit(1))
    row = result.first()
    assert row is not None
    evt = row[0]

    event_obj, hit = await EventService.get_event(session, str(evt.id))
    assert hit is False
    # second call should hit cache
    event_obj2, hit2 = await EventService.get_event(session, str(evt.id))
    assert hit2 is True
