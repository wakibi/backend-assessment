import uuid
from datetime import datetime

from fastapi import APIRouter, Response

from app.models import EventSyncPublic, EventSyncStart, EventsPublic, EventPublic, RedisDBHealthPublic
from app.api.deps import SessionDep
from app.api.routes.events.service import EventService


router = APIRouter(prefix="/events", tags=["events"])

@router.get("/events", response_model=EventsPublic)
async def get_events(
    session: SessionDep,
    limit: int = 100,
    offset: int =0,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    event_type: str | None = None,
    symbols: str | None = None
) -> EventsPublic:
    return await EventService.get_events(
        session=session,
        limit=limit,
        offset=offset,
        from_date=from_date,
        to_date=to_date,
        event_type=event_type,
        symbols=symbols
    )

@router.get("/events/{event_id}", response_model=EventPublic)
async def get_event(session: SessionDep, event_id: uuid.UUID, response: Response) -> EventPublic:
    event, hit = await EventService.get_event(
        session=session,
        event_id=event_id
    )
    response.headers["X-Cache"] = "HIT" if hit else "MISS"
    return event

@router.get("/health", response_model=RedisDBHealthPublic)
def check_services_health() -> RedisDBHealthPublic:
    return EventService.check_services_health()

@router.post("/events/sync", response_model=EventSyncPublic)
async def sync_events(session: SessionDep, request: EventSyncStart) -> EventSyncPublic:
    return await EventService.sync_events_for_symbols(session=session, symbols=request.symbols, force=request.force)
