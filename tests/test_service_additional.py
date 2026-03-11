import pytest
from datetime import datetime, timezone, timedelta
from sqlmodel import select

from app.api.routes.events.service import EventService
from app.models import Event, EventSymbol, EventType


@pytest.mark.asyncio
async def test_sync_creates_and_skips(db_session, monkeypatch):
    # stub providers to return single event per symbol
    event_template = {
        "event_id": "evt1",
        "symbol": "TEST",
        "event_type": "earnings",
        "event_date": "2026-03-15T00:00:00Z",
        "title": "Test",
        "details": {},
        # adapters tend to emit event_metadata key, support both
        "event_metadata": {},
    }

    class FakeProv:
        async def fetch_events(self, symbols, days_ahead=30):
            # return a copy so modifications don't propagate
            return [event_template.copy()]

    monkeypatch.setattr("app.api.routes.events.service.ProviderA", lambda: FakeProv())
    monkeypatch.setattr("app.api.routes.events.service.ProviderB", lambda: FakeProv())

    # first sync should create one event
    result = await EventService.sync_events_for_symbols(db_session, ["TEST"], force=False)
    assert result.status == "success"
    assert result.events_created == 1
    assert result.events_updated == 0
    assert result.symbols_synced == ["TEST"]
    assert result.symbols_skipped == []

    # second sync without force should skip the symbol
    result2 = await EventService.sync_events_for_symbols(db_session, ["TEST"], force=False)
    assert result2.events_created == 0
    assert result2.events_updated == 0
    assert result2.symbols_skipped == ["TEST"]

    # sync with force should fetch again and update
    result3 = await EventService.sync_events_for_symbols(db_session, ["TEST"], force=True)
    assert result3.events_updated == 1
    assert result3.symbols_skipped == []


@pytest.mark.asyncio
async def test_sync_error_on_provider(monkeypatch, db_session):
    class BrokenProv:
        async def fetch_events(self, symbols, days_ahead=30):
            raise Exception("boom")

    monkeypatch.setattr("app.api.routes.events.service.ProviderA", lambda: BrokenProv())
    monkeypatch.setattr("app.api.routes.events.service.ProviderB", lambda: BrokenProv())

    res = await EventService.sync_events_for_symbols(db_session, ["X"], force=True)
    assert res.status == "error"
    assert "boom" in res.errors[0]


@pytest.mark.asyncio
async def test_get_event_cache_flow(db_session):
    # ensure cache empty
    from app.settings.db import redis_client
    try:
        redis_client.flushdb()
    except Exception:
        pass

    # create an event manually
    session = db_session
    sym = EventSymbol(name="ZZZ")
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

    event_public, hit = await EventService.get_event(session, str(evt.id))
    assert not hit
    event_public2, hit2 = await EventService.get_event(session, str(evt.id))
    assert hit2
