"""Unit tests for the core event/attendance rules (no Discord involved)."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from database.models import EventStatus, EventType, ResponseState
from services import event_service
from services.errors import (
    EventLockedError,
    EventStateError,
    ResponseValidationError,
)

DAY = date(2026, 6, 21)
DEADLINE = datetime(2026, 6, 21, 23, 0, tzinfo=timezone.utc)


async def _event(session):
    return await event_service.get_or_create_event(
        session, event_date=DAY, lock_deadline=DEADLINE, channel_id=123
    )


async def test_get_or_create_event_is_idempotent(session):
    e1 = await _event(session)
    e2 = await event_service.get_or_create_event(
        session, event_date=DAY, lock_deadline=DEADLINE
    )
    assert e1.id == e2.id
    assert e1.event_type is EventType.PRACTICE
    assert e1.status is EventStatus.OPEN


async def test_set_response_upserts_single_row(session):
    event = await _event(session)
    r1 = await event_service.set_response(
        session, event, discord_id=1, display_name="A", state=ResponseState.AVAILABLE
    )
    r2 = await event_service.set_response(
        session, event, discord_id=1, display_name="A", state=ResponseState.UNAVAILABLE
    )
    assert r1.id == r2.id
    responses = await event_service.list_responses(session, event)
    assert len(responses) == 1
    assert responses[0].state is ResponseState.UNAVAILABLE


async def test_late_requires_eta(session):
    event = await _event(session)
    with pytest.raises(ResponseValidationError):
        await event_service.set_response(
            session, event, discord_id=1, display_name="A", state=ResponseState.LATE
        )


async def test_late_stores_eta_and_clears_on_switch(session):
    event = await _event(session)
    r = await event_service.set_response(
        session,
        event,
        discord_id=1,
        display_name="A",
        state=ResponseState.LATE,
        eta="15 min",
    )
    assert r.eta == "15 min"
    r = await event_service.set_response(
        session, event, discord_id=1, display_name="A", state=ResponseState.AVAILABLE
    )
    assert r.eta is None


async def test_locked_event_rejects_response(session):
    event = await _event(session)
    await event_service.lock_event(session, event, locked_by=999)
    assert event.status is EventStatus.LOCKED
    assert event.locked_by == 999
    with pytest.raises(EventLockedError):
        await event_service.set_response(
            session, event, discord_id=1, display_name="A", state=ResponseState.AVAILABLE
        )


async def test_unlock_reopens_event(session):
    event = await _event(session)
    await event_service.lock_event(session, event)
    await event_service.unlock_event(session, event)
    assert event.status is EventStatus.OPEN
    r = await event_service.set_response(
        session, event, discord_id=1, display_name="A", state=ResponseState.AVAILABLE
    )
    assert r.state is ResponseState.AVAILABLE


async def test_set_event_type_blocked_when_locked(session):
    event = await _event(session)
    await event_service.set_event_type(session, event, EventType.MATCH)
    assert event.event_type is EventType.MATCH
    await event_service.lock_event(session, event)
    with pytest.raises(EventStateError):
        await event_service.set_event_type(session, event, EventType.PRACTICE)


async def test_get_non_responders(session):
    event = await _event(session)
    await event_service.set_response(
        session, event, discord_id=1, display_name="A", state=ResponseState.AVAILABLE
    )
    non = await event_service.get_non_responders(session, event, [1, 2, 3])
    assert set(non) == {2, 3}


async def test_event_has_default_and_settable_start_time(session):
    event = await _event(session)
    assert event.start_time == "19:00"
    await event_service.set_event_start_time(session, event, "20:30")
    assert event.start_time == "20:30"
    # Allowed even when locked.
    await event_service.lock_event(session, event)
    await event_service.set_event_start_time(session, event, "18:15")
    assert event.start_time == "18:15"


async def test_display_name_is_refreshed(session):
    event = await _event(session)
    await event_service.set_response(
        session, event, discord_id=1, display_name="Old", state=ResponseState.AVAILABLE
    )
    player = await event_service.get_or_create_player(
        session, discord_id=1, display_name="New"
    )
    assert player.display_name == "New"
