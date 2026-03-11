import pytest
import asyncio

from app.integration.providers import ProviderA, ProviderB


@pytest.mark.asyncio
async def test_provider_a_adapter_basic():
    sample = {
        "event_id": "pa-foo-earnings-202602",
        "ticker": "FOO",
        "type": "earnings",
        "date": "2026-02-20",
        "time": "14:00:00",
        "title": "Foo Earnings",
        "details": {"eps_estimate": 1.23},
        "metadata": {"foo": "bar"},
    }
    prov = ProviderA()
    out = prov.adapter(sample)
    # normalized keys
    assert out["event_id"] == sample["event_id"]
    assert out["symbol"] == "FOO"
    assert "event_date" in out
    assert out["event_type"] == "earnings"
    assert out["title"] == sample["title"]
    assert out["details"] == sample["details"]
    # mappings now expose event_metadata instead of metadata key
    assert out["event_metadata"] == sample["metadata"]


@pytest.mark.asyncio
async def test_provider_b_adapter_basic():
    sample = {
        "id": "pb_foo",
        "instrument": {"symbol": "FOO", "exchange": "NASDAQ"},
        "event": {
            "category": "earnings_release",
            "scheduled_at": "2026-03-01T12:00:00Z",
            "title": "Foo Earnings",
            "description": "desc",
            "earnings_data": {"eps_consensus": 2.34},
        },
        "provider_metadata": {"quality_score": 90},
    }
    prov = ProviderB()
    out = prov.adapter(sample)
    assert out["event_id"] == sample["id"]
    assert out["symbol"] == "FOO"
    assert out["exchange"] == "NASDAQ"
    assert out["event_type"] == "earnings_release"
    assert out["title"] == sample["event"]["title"]
    assert out["description"] == "desc"
    assert out["details"]["eps_consensus"] == 2.34
    assert out["event_metadata"] == sample["provider_metadata"]


@pytest.mark.asyncio
async def test_provider_a_fetch_and_get(monkeypatch):
    # stub underlying client behaviour to avoid randomness
    async def fake_fetch(symbols, days_ahead=30):
        return [{
            "event_id": "pa-test",
            "ticker": symbols[0],
            "type": "earnings",
            "date": "2026-02-20",
            "time": None,
            "title": "T",
            "details": {},
            "metadata": {},
        }]

    async def fake_get(event_id):
        return {
            "event_id": event_id,
            "ticker": "FOO",
            "type": "dividend",
            "date": "2026-02-25",
            "title": "X",
            "metadata": {},
        }

    prov = ProviderA()
    prov.client.fetch_events = fake_fetch
    prov.client.get_event = fake_get

    events = await prov.fetch_events(["FOO"])
    assert isinstance(events, list)
    assert events[0]["symbol"] == "FOO"

    e = await prov.get_event("whatever")
    assert e["symbol"] == "FOO"


@pytest.mark.asyncio
async def test_provider_b_fetch_and_get(monkeypatch):
    async def fake_fetch(symbols, days_ahead=30, cursor=None, page_size=20):
        return {
            "events": [
                {
                    "id": "pb-test",
                    "instrument": {"symbol": symbols[0], "exchange": "NYSE"},
                    "event": {"category": "dividend_payment", "scheduled_at": "2026-04-01T00:00:00Z", "title": "T"},
                    "provider_metadata": {},
                }
            ],
            "pagination": {"has_next": False, "next_cursor": None},
            "meta": {},
        }

    async def fake_get(event_id):
        return {
            "id": event_id,
            "instrument": {"symbol": "BAR", "exchange": "NYSE"},
            "event": {"category": "dividend_payment", "scheduled_at": "2026-04-01T00:00:00Z", "title": "T"},
            "provider_metadata": {},
        }

    prov = ProviderB()
    prov.client.fetch_events = fake_fetch
    prov.client.get_event = fake_get

    events = await prov.fetch_events(["BAR"])
    assert isinstance(events, list)
    assert events[0]["symbol"] == "BAR"

    e = await prov.get_event("foo")
    assert e["symbol"] == "BAR"
