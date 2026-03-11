# Market Events Service

Build a FastAPI service that aggregates financial market events (earnings, dividends, splits) from multiple providers and exposes a unified API.

**Time:** 2-3 days

## What You're Building

A service that:
- Fetches events from two external providers (simulated in `providers/`)
- Normalizes their different formats into a unified schema
- Stores in PostgreSQL with deduplication
- Caches with Redis
- Exposes a REST API

## API Spec

### `GET /api/v1/events`

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `symbols` | string | No | Comma-separated (e.g., `AAPL,MSFT`) |
| `event_type` | string | No | `earnings`, `dividend`, `economic`, `split` |
| `from_date` | string | No | YYYY-MM-DD |
| `to_date` | string | No | YYYY-MM-DD |
| `limit` | int | No | Default 50, max 500 |
| `offset` | int | No | Pagination offset |

Response:
```json
{
  "data": [
    {
      "id": "uuid",
      "symbol": "AAPL",
      "event_type": "earnings",
      "event_date": "2026-02-20",
      "title": "Q1 2026 Earnings Release",
      "details": {},
      "created_at": "2026-02-15T10:30:00Z"
    }
  ],
  "total": 150,
  "limit": 50,
  "offset": 0,
  "has_more": true
}
```

Include `X-Cache: HIT` or `X-Cache: MISS` header.

### `GET /api/v1/events/{event_id}`

Single event by ID.

### `POST /api/v1/events/sync`

```json
{
  "symbols": ["AAPL", "MSFT"],
  "force": false
}
```

Response:
```json
{
  "status": "completed",
  "symbols_synced": ["AAPL", "MSFT"],
  "symbols_skipped": [],
  "events_created": 12,
  "events_updated": 3,
  "errors": []
}
```

- `force: false` skips symbols synced in the last hour
- `force: true` always fetches fresh

### `GET /api/v1/health`

Service health with Redis/DB status.

## Providers

The `providers/` folder contains two simulated external APIs. They have different interfaces and return different data formats.

**Don't modify anything in `providers/`** - treat them like external APIs you can't control.


Check the docstrings for details on rate limits and error handling.

## Data Model

Design your schema considering:
- Both providers might return the same real-world event with different IDs
- You need deduplication
- Query by symbol, date range, type

## Deliverables

1. Working service (`docker-compose up` should work)
2. Your README with setup instructions and architecture notes
3. Tests for core logic

## Setup

```bash
docker-compose up -d
cp .env.example .env
poetry install
poetry run uvicorn app.main:app --reload --port 8000
```

## Questions?

If something's unclear, document your assumptions and move on. 


## Assumptions
- uuid is a UUID not event_id as returned by external APIs
- date as returned in provider_a is the event_date in our API, ticker -> symbol. Created at in the API is the timestamp the data was actually imported from the providers.
- Provider A date is in UTC