import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from sqlmodel import DateTime, Field, JSON, SQLModel
from sqlalchemy import Index, func



def get_utc_now() -> datetime:
    return datetime.now(timezone.utc)

class EventBase(SQLModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(
        sa_type=DateTime(timezone=True), default_factory=lambda: datetime.now(timezone.utc)
    )
    # automatically set on insert; SQLAlchemy onupdate will refresh
    updated_at: datetime | None = Field(
        sa_type=DateTime(timezone=True),
        default_factory=get_utc_now,
        sa_column_kwargs={"onupdate": get_utc_now},
    )


class EventAttribute(EventBase):
    name: str = Field(unique=True)


class EventType(EventAttribute, table=True):
    pass


class EventSymbol(EventAttribute, table=True):
    pass


class EventExchange(EventAttribute, table=True):
    pass


class Event(EventBase, table=True):
    event_id: str
    symbol: int = Field(foreign_key="eventsymbol.id")
    event_type: int = Field(foreign_key="eventtype.id")
    event_date: datetime = Field(sa_type=DateTime(timezone=True))
    title: str
    details: Dict[str, Any] | None = Field(sa_type=JSON)
    event_metadata: Dict[str, Any] = Field(sa_type=JSON)
    description: str | None
    exchange: int | None = Field(foreign_key="eventexchange.id")

    __table_args__ = (Index('idx_event_dedupe', 'symbol', 'event_type', func.date('event_date')), )


class EventPublic(SQLModel):
    id: str
    symbol: str
    event_type: str
    event_date: str
    title: str
    details: Dict[str, Any] = Field(sa_type=JSON, default={})
    created_at: datetime = Field(sa_type=DateTime(timezone=True))


class EventsPublic(SQLModel):
    data: list[EventPublic]
    total: int
    limit: int
    offset: int
    has_more: bool


class EventSyncStart(SQLModel):
    symbols: list[str]
    force: bool


class EventSyncPublic(SQLModel):
    status: str
    symbols_synced: list[str]
    symbols_skipped: list[str]
    events_created: int
    events_updated: int
    errors: list[str]


class RedisDBHealthPublic(SQLModel):
    redis: dict[str, str]
    db: dict[str, str]
