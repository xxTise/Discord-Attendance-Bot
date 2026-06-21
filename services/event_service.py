"""Core business logic for daily check-in events.

All functions operate on an :class:`~sqlalchemy.ext.asyncio.AsyncSession` and plain
data (IDs, enums, strings). They never touch ``discord.py`` objects, which keeps the
rules unit-testable. Captain authorization is enforced in the cog layer; these
functions only enforce event-state invariants.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date, datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import (
    Event,
    EventStatus,
    EventType,
    Player,
    Response,
    ResponseState,
)
from services.errors import EventLockedError, EventStateError, ResponseValidationError
from utils.time_utils import utcnow


async def get_or_create_player(
    session: AsyncSession, *, discord_id: int, display_name: str
) -> Player:
    """Return the player for ``discord_id``, creating it on first sight.

    Keeps ``display_name`` fresh so historical reports show current names.
    """
    player = await session.scalar(
        select(Player).where(Player.discord_id == discord_id)
    )
    if player is None:
        player = Player(discord_id=discord_id, display_name=display_name)
        session.add(player)
        await session.flush()
    elif display_name and player.display_name != display_name:
        player.display_name = display_name
    return player


async def get_event_by_date(
    session: AsyncSession, event_date: date
) -> Optional[Event]:
    """Return the event for a given date, or ``None``."""
    return await session.scalar(
        select(Event).where(Event.event_date == event_date)
    )


async def get_event_by_message_id(
    session: AsyncSession, message_id: int
) -> Optional[Event]:
    """Return the event whose check-in embed is ``message_id``, or ``None``."""
    return await session.scalar(
        select(Event).where(Event.message_id == message_id)
    )


async def get_or_create_event(
    session: AsyncSession,
    *,
    event_date: date,
    lock_deadline: datetime,
    start_time: str = "19:00",
    channel_id: Optional[int] = None,
    default_type: EventType = EventType.PRACTICE,
) -> Event:
    """Return today's event, creating it (OPEN, Practice) if it does not exist.

    The unique constraint on ``event_date`` guarantees a single event per day even
    if the scheduler and a manual ``/checkin`` race.
    """
    event = await get_event_by_date(session, event_date)
    if event is None:
        event = Event(
            event_date=event_date,
            event_type=default_type,
            start_time=start_time,
            status=EventStatus.OPEN,
            lock_deadline=lock_deadline,
            channel_id=channel_id,
        )
        session.add(event)
        await session.flush()
    return event


async def set_event_start_time(
    session: AsyncSession,
    event: Event,
    start_time: str,
    *,
    lock_deadline: Optional[datetime] = None,
) -> Event:
    """Set the kickoff time (``"HH:MM"``), optionally moving the lock deadline too.

    Allowed regardless of lock state.
    """
    event.start_time = start_time
    if lock_deadline is not None:
        event.lock_deadline = lock_deadline
    # Kickoff moved — let pre-kickoff pings re-evaluate against the new time.
    event.pinged_offsets = ""
    await session.flush()
    return event


async def set_response(
    session: AsyncSession,
    event: Event,
    *,
    discord_id: int,
    display_name: str,
    state: ResponseState,
    eta: Optional[str] = None,
) -> Response:
    """Create or update a player's response (upsert, one row per player per event).

    Raises:
        EventLockedError: if the event is locked.
        ResponseValidationError: if ``state`` is LATE without an ETA.
    """
    if event.status is EventStatus.LOCKED:
        raise EventLockedError(
            "This check-in is locked; responses can no longer be changed."
        )
    if state is ResponseState.LATE and not (eta and eta.strip()):
        raise ResponseValidationError("An ETA is required for a Late response.")

    normalized_eta = eta.strip() if state is ResponseState.LATE else None
    player = await get_or_create_player(
        session, discord_id=discord_id, display_name=display_name
    )
    response = await session.scalar(
        select(Response).where(
            Response.event_id == event.id, Response.player_id == player.id
        )
    )
    if response is None:
        response = Response(
            event_id=event.id,
            player_id=player.id,
            state=state,
            eta=normalized_eta,
        )
        session.add(response)
    else:
        response.state = state
        response.eta = normalized_eta
        response.updated_at = utcnow()
    await session.flush()
    return response


async def list_responses(session: AsyncSession, event: Event) -> Sequence[Response]:
    """Return all responses for an event, with each response's player loaded."""
    result = await session.scalars(
        select(Response)
        .where(Response.event_id == event.id)
        .options(selectinload(Response.player))
    )
    return result.all()


async def lock_event(
    session: AsyncSession, event: Event, *, locked_by: Optional[int] = None
) -> Event:
    """Lock an event so responses become read-only.

    ``locked_by`` is the captain's Discord ID, or ``None`` for an automatic lock.
    """
    event.status = EventStatus.LOCKED
    event.locked_at = utcnow()
    event.locked_by = locked_by
    await session.flush()
    return event


async def unlock_event(session: AsyncSession, event: Event) -> Event:
    """Reopen a locked event."""
    event.status = EventStatus.OPEN
    event.locked_at = None
    event.locked_by = None
    await session.flush()
    return event


async def set_event_type(
    session: AsyncSession, event: Event, event_type: EventType
) -> Event:
    """Change an event's type. Disallowed once locked."""
    if event.status is EventStatus.LOCKED:
        raise EventStateError(
            "Cannot change event type after the check-in is locked."
        )
    event.event_type = event_type
    await session.flush()
    return event


async def get_non_responders(
    session: AsyncSession, event: Event, member_ids: Iterable[int]
) -> list[int]:
    """Return the Discord IDs in ``member_ids`` that have no response for the event."""
    responses = await list_responses(session, event)
    responded_discord_ids = {r.player.discord_id for r in responses}
    return [m for m in member_ids if m not in responded_discord_ids]
