"""Tests for time parsing/formatting and embed rendering (12-hour clock)."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

import pytest

from database.models import Event, EventStatus, EventType
from utils.time_utils import (
    due_ping_offsets,
    format_ampm,
    lock_deadline_from_kickoff,
    parse_time_flexible,
)
from views.embeds import build_checkin_embed


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("19:00", time(19, 0)),
        ("7:00 PM", time(19, 0)),
        ("7pm", time(19, 0)),
        ("7:30 am", time(7, 30)),
        ("00:15", time(0, 15)),
    ],
)
def test_parse_time_flexible(raw, expected):
    assert parse_time_flexible(raw) == expected


def test_parse_time_flexible_rejects_garbage():
    with pytest.raises(ValueError):
        parse_time_flexible("not a time")


@pytest.mark.parametrize(
    "value,expected",
    [
        (time(19, 0), "7:00 PM"),
        (time(0, 0), "12:00 AM"),
        (time(12, 0), "12:00 PM"),
        (time(9, 5), "9:05 AM"),
    ],
)
def test_format_ampm(value, expected):
    assert format_ampm(value) == expected


def test_lock_deadline_is_one_hour_before_kickoff():
    # 7:00 PM CT kickoff, 60-min offset -> 6:00 PM CDT == 23:00 UTC (June).
    deadline = lock_deadline_from_kickoff(
        date(2026, 6, 21), "19:00", "America/Chicago", 60
    )
    assert deadline == datetime(2026, 6, 21, 23, 0, tzinfo=timezone.utc)


def test_lock_deadline_tracks_changed_kickoff():
    # Move kickoff to 8:30 PM CT -> lock 7:30 PM CDT == 00:30 UTC next day.
    deadline = lock_deadline_from_kickoff(
        date(2026, 6, 21), "20:30", "America/Chicago", 60
    )
    assert deadline == datetime(2026, 6, 22, 0, 30, tzinfo=timezone.utc)


def test_due_ping_offsets_windows():
    kickoff = datetime(2026, 6, 22, 0, 0, tzinfo=timezone.utc)  # midnight UTC
    offsets = [60, 30]
    # 60 min before: only the 60 ping is due.
    assert due_ping_offsets(kickoff - timedelta(minutes=60), kickoff, offsets, set()) == [60]
    # 30 min before with 60 already sent: only 30 is due.
    assert due_ping_offsets(kickoff - timedelta(minutes=30), kickoff, offsets, {60}) == [30]
    # At/after kickoff: nothing fires.
    assert due_ping_offsets(kickoff, kickoff, offsets, set()) == []
    # Long before kickoff: nothing due yet.
    assert due_ping_offsets(kickoff - timedelta(minutes=90), kickoff, offsets, set()) == []


def test_prekickoff_schedule():
    from bot.checkin_manager import PREKICKOFF_SCHEDULE

    by_offset = {p.offset_minutes: p for p in PREKICKOFF_SCHEDULE}
    assert by_offset[75].target == "no-response"
    assert "15 minutes" in by_offset[75].message
    assert by_offset[60].target == "everyone"
    assert "locked" in by_offset[60].message.lower()
    assert by_offset[30].target == "available"
    assert "lobby up" in by_offset[30].message.lower()


def test_embed_shows_kickoff_in_12h():
    event = Event(
        event_date=date(2026, 6, 21),
        event_type=EventType.LEAGUE_MATCH,
        start_time="19:00",
        status=EventStatus.OPEN,
        lock_deadline=datetime(2026, 6, 21, 23, 0, tzinfo=timezone.utc),
    )
    embed = build_checkin_embed(
        event, [], tz_name="America/Chicago", tz_label="CT"
    )
    assert "League Match" in embed.title
    assert "Kickoff:** 7:00 PM CT" in embed.description
    # 23:00 UTC == 6:00 PM CT (CDT, UTC-5) in June
    assert "Responses lock at 6:00 PM CT" in embed.footer.text
