from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import SQLModel, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.models import Event, EventSymbol, EventType
from app.api.routes.events.service import EventService



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
        event_metadata={},
        description=None,
        exchange=None,
    )
    e2 = Event(
        event_id="e2",
        symbol=sym.id,
        event_type=typ.id,
        event_date=base_date + timedelta(days=1),
        title="Second",
        details={"foo": "bar"},
        event_metadata={},
        description=None,
        exchange=None,
    )
    session.add_all([e1, e2])
    await session.commit()


@pytest.mark.asyncio
async def test_get_events_basic(db_session):
    session = db_session
    await seed_data(session)
    result = await EventService.get_events(session)
    assert result.total == 2
    assert len(result.data) == 2
    assert result.has_more is False
    assert result.data[0].symbol == "AAPL"
    assert result.data[0].event_type == "earnings"


@pytest.mark.asyncio
async def test_get_events_pagination(db_session):
    session = db_session
    await seed_data(session)
    res1 = await EventService.get_events(session, limit=1, offset=0)
    assert res1.total == 2
    assert len(res1.data) == 1
    assert res1.has_more is True
    res2 = await EventService.get_events(session, limit=1, offset=1)
    assert len(res2.data) == 1
    assert res2.has_more is False


@pytest.mark.asyncio
async def test_get_events_filters(db_session):
    session = db_session
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
async def test_invalid_params(db_session):
    session = db_session
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
async def test_get_event_caching(db_session):
    # ensure redis is cleared or skip if unavailable
    session = db_session
    from app.settings.db import redis_client
    try:
        redis_client.flushdb()
    except Exception:
        pytest.skip("redis not available")

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
