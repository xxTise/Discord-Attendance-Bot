"""Tests for time parsing/formatting and embed rendering (12-hour clock)."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

import pytest

from database.models import (
    Event,
    EventStatus,
    EventType,
    Player,
    Response,
    ResponseState,
)
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


def _event(status=EventStatus.OPEN):
    return Event(
        event_date=date(2026, 6, 21),
        event_type=EventType.LEAGUE_MATCH,
        start_time="19:00",
        status=status,
        lock_deadline=datetime(2026, 6, 21, 23, 0, tzinfo=timezone.utc),
    )


def _resp(state, name):
    r = Response(state=state, eta=None)
    r.player = Player(discord_id=1, display_name=name)
    return r


def _field(embed, needle):
    return next(f.value for f in embed.fields if needle in f.name)


def test_embed_premium_layout():
    embed = build_checkin_embed(
        _event(), [], tz_name="America/Chicago", tz_label="CT", squad_size=11
    )
    assert "League Match" in embed.title
    assert "7:00 PM CT" in _field(embed, "Kickoff")
    squad = _field(embed, "Squad")
    assert "0/11" in squad and "⬜" in squad
    # 23:00 UTC == 6:00 PM CT (CDT) in June
    assert "Locks at 6:00 PM CT" in embed.footer.text


def test_progress_bar_counts_available():
    responses = [_resp(ResponseState.AVAILABLE, f"P{i}") for i in range(3)]
    responses.append(_resp(ResponseState.UNAVAILABLE, "X"))
    embed = build_checkin_embed(
        _event(), responses, tz_name="America/Chicago", tz_label="CT", squad_size=11
    )
    squad = _field(embed, "Squad")
    assert squad.count("🟩") == 3
    assert squad.count("⬜") == 8
    assert "3/11" in squad
    assert "P0" in _field(embed, "Available")
    assert "X" in _field(embed, "Out")


def test_progress_bar_full_squad():
    responses = [_resp(ResponseState.AVAILABLE, f"P{i}") for i in range(11)]
    embed = build_checkin_embed(
        _event(), responses, tz_name="America/Chicago", tz_label="CT", squad_size=11
    )
    squad = _field(embed, "Squad")
    assert squad.count("🟩") == 11
    assert squad.count("⬜") == 0
    assert "FULL SQUAD" in squad


def test_embed_ignores_legacy_late_rows():
    # Late was removed; old LATE rows must not crash or appear.
    responses = [
        _resp(ResponseState.AVAILABLE, "Ava"),
        _resp(ResponseState.LATE, "Legacy"),
    ]
    embed = build_checkin_embed(
        _event(), responses, tz_name="America/Chicago", tz_label="CT", squad_size=11
    )
    assert "Legacy" not in str(embed.to_dict())
    assert "Ava" in _field(embed, "Available")
