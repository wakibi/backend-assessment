from datetime import datetime, timezone, timedelta
from typing import Any, List, Type, TypeVar

import asyncio
from fastapi import HTTPException
from sqlmodel import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Event, EventSyncPublic, EventsPublic, EventPublic, EventSymbol, EventType, EventExchange, RedisDBHealthPublic
from app.integration.providers import ProviderA, ProviderB
from app.utils.utils import check_db_status, check_redis_status
from app.settings.db import engine, redis_client
import json

T = TypeVar("T")  # generic type for _get_or_create



class EventService:
    @staticmethod
    async def get_events(
        session: AsyncSession,
        limit: int = 100,
        offset: int =0,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        event_type: str | None = None,
        symbols: str | None = None
    ) -> EventsPublic:
        # pagination validation
        if limit < 1:
            raise HTTPException(status_code=400, detail="limit must be >= 1")
        if limit > 500:
            limit = 500  # cap to API spec

        if from_date and to_date and from_date > to_date:
            raise HTTPException(status_code=400, detail="from_date must be <= to_date")

        if to_date is not None:
            to_date = to_date.replace(hour=23, minute=59, second=59, microsecond=999999)

        filters: List[Any] = []
        if from_date:
            filters.append(Event.event_date >= from_date)
        if to_date:
            filters.append(Event.event_date <= to_date)

        symbol_list: List[str] = []
        if symbols:
            symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
            if symbol_list:
                lower_syms = [s.lower() for s in symbol_list]
                filters.append(func.lower(EventSymbol.name).in_(lower_syms))

        type_list: List[str] = []
        if event_type:
            type_list = [s.strip() for s in event_type.split(",") if s.strip()]
            if type_list:
                lower_types = [t.lower() for t in type_list]
                filters.append(func.lower(EventType.name).in_(lower_types))

        count_stmt = select(func.count()).select_from(Event)
        if symbol_list:
            count_stmt = count_stmt.join(EventSymbol, Event.symbol == EventSymbol.id)
        if type_list:
            count_stmt = count_stmt.join(EventType, Event.event_type == EventType.id)
        if filters:
            count_stmt = count_stmt.where(*filters)

        result = await session.execute(count_stmt)
        total = result.scalar_one()

        data_stmt = (
            select(Event, EventSymbol.name, EventType.name)
            .join(EventSymbol, Event.symbol == EventSymbol.id)
            .join(EventType, Event.event_type == EventType.id)
        )
        if filters:
            data_stmt = data_stmt.where(*filters)

        data_stmt = data_stmt.order_by(Event.event_date).offset(offset).limit(limit)
        result = await session.execute(data_stmt)
        rows = result.all()

        events: list[EventPublic] = []
        for row in rows:
            if isinstance(row, tuple):
                event_obj, symbol_name, type_name = row
            else:
                event_obj = row
                symbol_name = ""
                type_name = ""

            events.append(
                EventPublic(
                    id=str(event_obj.id),
                    symbol=symbol_name,
                    event_type=type_name,
                    event_date=event_obj.event_date.date().isoformat(),
                    title=event_obj.title,
                    details=event_obj.details or {},
                    created_at=event_obj.created_at,
                )
            )

        has_more = offset + len(events) < total
        return EventsPublic(
            data=events,
            total=total,
            limit=limit,
            offset=offset,
            has_more=has_more,
        )

    @staticmethod
    async def get_event(
        session: AsyncSession,
        event_id: str
    ) -> tuple[EventPublic, bool]:
        """Return (event, cache_hit).

        First check Redis, if present return cached event with hit=True.  Otherwise
        load from the database, cache the serialized result, and return hit=False.
        """
        event_id = str(event_id)
        key = f"event:{event_id}"
        raw = redis_client.get(key)
        if raw:
            try:
                data = json.loads(raw)
                event = EventPublic(**data)
                return event, True
            except Exception:  # fall through to DB if cache corrupt
                pass

        stmt = (
            select(Event, EventSymbol.name, EventType.name)
            .where(Event.id == event_id)
            .join(EventSymbol, Event.symbol == EventSymbol.id)
            .join(EventType, Event.event_type == EventType.id)
        )
        row = (await session.execute(stmt)).first()
        if not row:
            raise HTTPException(status_code=404, detail="Event not found")

        event_obj, symbol_name, type_name = row
        event = EventPublic(
            id=str(event_obj.id),
            symbol=symbol_name,
            event_type=type_name,
            event_date=event_obj.event_date.date().isoformat(),
            title=event_obj.title,
            details=event_obj.details or {},
            created_at=event_obj.created_at,
        )
        # cache for next time
        redis_client.set(key, json.dumps(event.dict()))
        return event, False
        
    @staticmethod
    async def _partition_symbols(
        session: AsyncSession,
        symbols: List[str],
        force: bool
    ) -> tuple[List[str], List[str]]:
        """Return two lists: to_sync and skipped based on updated_at and force flag.

        If ``force`` is True we short‑circuit and sync everything. Otherwise we
        perform a single query for records that have been updated within the last
        hour; those are considered *skipped*. Everything else (including symbols
        that do not yet exist in the table) is earmarked for syncing.
        """
        if force:
            return symbols.copy(), []

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=1)

        # symbols recently updated -> skip
        stmt = (
            select(EventSymbol.name)
            .where(
                EventSymbol.name.in_(symbols),
                EventSymbol.updated_at != None,
                EventSymbol.updated_at > cutoff,
            )
        )
        recent = set((await session.scalars(stmt)).all())

        to_sync: List[str] = []
        skipped: List[str] = []
        for sym in symbols:
            if sym in recent:
                skipped.append(sym)
            else:
                to_sync.append(sym)
        return to_sync, skipped

    @staticmethod
    async def _mark_symbol_updated(session: AsyncSession, symbol: str, when: datetime) -> None:
        stmt = select(EventSymbol).where(EventSymbol.name == symbol)
        sym = await session.scalar(stmt)
        if sym:
            sym.updated_at = when
            await session.commit()

    @staticmethod
    async def _get_or_create(session: AsyncSession, model: Type[T], **kwargs) -> T:
        """Generic helper that returns existing object or creates a new one."""
        stmt = select(model).filter_by(**kwargs)
        obj = await session.scalar(stmt)
        if obj:
            return obj
        obj = model(**kwargs)
        session.add(obj)
        await session.commit()
        await session.refresh(obj)
        return obj

    @staticmethod
    async def sync_events_for_symbols(
        session: AsyncSession,
        symbols: List[str],
        force: bool = False
    ) -> EventSyncPublic:
        """
        - force: false skips symbols synced in the last hour
        - force: true always fetches fresh
        """
        to_sync, skipped = EventService._partition_symbols(session, symbols, force)
        now = datetime.now(timezone.utc)  # still needed later for timestamps
        
        if not to_sync:
            return EventSyncPublic(
                status="success",
                symbols_synced=[],
                symbols_skipped=skipped,
                events_created=0,
                events_updated=0,
                errors=[]
            )
        
        
        try:
            provider_a = ProviderA()
            provider_b = ProviderB()
            events_a, events_b = await asyncio.gather(
                provider_a.fetch_events(to_sync, days_ahead=30),
                provider_b.fetch_events(to_sync, days_ahead=30),
            )
            events = events_a + events_b
        except Exception as e:
            return EventSyncPublic(
                status="error",
                symbols_synced=[],
                symbols_skipped=skipped,
                events_created=0,
                events_updated=0,
                errors=[str(e)]
            )
        
        events_created = 0
        events_updated = 0
        for event in events:
            if event['symbol'] not in to_sync:
                continue
            
            # providers send UTC strings, ensure we store aware UTC datetime
            event_date = event['event_date']
            if isinstance(event_date, str):
                event_date = datetime.fromisoformat(event_date.replace('Z', '+00:00'))
            # ensure timezone info
            if event_date.tzinfo is None:
                event_date = event_date.replace(tzinfo=timezone.utc)
            else:
                # normalize to UTC
                event_date = event_date.astimezone(timezone.utc)

            # get or create EventSymbol, EventType, EventExchange
            sym = await EventService._get_or_create(session, EventSymbol, name=event['symbol'])
            typ = await EventService._get_or_create(session, EventType, name=event['event_type'])
            exch = None
            if event.get('exchange'):
                exch = await EventService._get_or_create(session, EventExchange, name=event['exchange'])
            
            # check if Event exists by symbol, event_type, and event_date (day)
            evt_stmt = select(Event).where(
                Event.symbol == sym.id,
                Event.event_type == typ.id,
                func.date(Event.event_date) == event_date.date()
            )
            existing = await session.scalar(evt_stmt)
            if existing:
                # update
                existing.event_id = event['event_id']
                existing.symbol = sym.id
                existing.event_type = typ.id
                existing.event_date = event_date
                existing.title = event['title']
                existing.details = event.get('details', {})
                existing.metadata = event.get('metadata', {})
                existing.description = event.get('description')
                existing.exchange = exch.id if exch else None
                existing.updated_at = now
                await session.commit()
                events_updated += 1
                db_id = existing.id
            else:
                # create
                new_evt = Event(
                    event_id=event['event_id'],
                    symbol=sym.id,
                    event_type=typ.id,
                    event_date=event_date,
                    title=event['title'],
                    details=event.get('details', {}),
                    metadata=event.get('metadata', {}),
                    description=event.get('description'),
                    exchange=exch.id if exch else None
                )
                session.add(new_evt)
                await session.commit()
                await session.refresh(new_evt)
                events_created += 1
                db_id = new_evt.id
            
            # cache in redis
            # use the normalized datetime when building the public representation
            event_public = EventPublic(
                id=str(db_id),
                symbol=event['symbol'],
                event_type=event['event_type'],
                event_date=event_date.date().isoformat(),
                title=event['title'],
                details=event.get('details', {}),
                created_at=now
            )
            redis_client.set(f"event:{db_id}", json.dumps(event_public.dict()))

        # update updated_at for synced symbols
        for symbol in to_sync:
            await EventService._mark_symbol_updated(session, symbol, now)
        return EventSyncPublic(
            status="success",
            symbols_synced=to_sync,
            symbols_skipped=skipped,
            events_created=events_created,
            events_updated=events_updated,
            errors=[]
        )

    @staticmethod
    def check_services_health() -> RedisDBHealthPublic:
        db_status = check_db_status(engine)
        redis_status = check_redis_status(redis_client)
        return RedisDBHealthPublic(redis=redis_status, db=db_status)
