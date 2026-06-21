"""Timezone-aware time helpers.

All datetimes are stored and compared in UTC. Local times (e.g. "12:00 CT") are
interpreted in the configured timezone and converted to UTC at the edges.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


def utcnow() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def parse_hhmm(value: str) -> time:
    """Parse a ``"HH:MM"`` string into a :class:`datetime.time`."""
    hours, minutes = value.split(":")
    return time(int(hours), int(minutes))


def parse_time_flexible(value: str) -> time:
    """Parse a human time like ``"7pm"``, ``"7:00 PM"``, or ``"19:00"``.

    Raises ``ValueError`` if none of the accepted formats match.
    """
    cleaned = value.strip().upper().replace(" ", "")
    for fmt in ("%H:%M", "%I:%M%p", "%I%p"):
        try:
            return datetime.strptime(cleaned, fmt).time()
        except ValueError:
            continue
    raise ValueError(f"Unrecognized time: {value!r}")


def format_ampm(value: time) -> str:
    """Format a time as a 12-hour clock string, e.g. ``"7:00 PM"``."""
    hour = value.hour % 12 or 12
    suffix = "AM" if value.hour < 12 else "PM"
    return f"{hour}:{value.minute:02d} {suffix}"


def today_in_tz(tz_name: str) -> date:
    """Return today's calendar date in the given timezone."""
    return datetime.now(ZoneInfo(tz_name)).date()


def at_local_time_utc(day: date, hhmm: str, tz_name: str) -> datetime:
    """Convert a local wall-clock time on ``day`` to a UTC datetime."""
    tz = ZoneInfo(tz_name)
    local_dt = datetime.combine(day, parse_hhmm(hhmm), tzinfo=tz)
    return local_dt.astimezone(timezone.utc)


def lock_deadline_from_kickoff(
    event_date: date, start_time: str, tz_name: str, offset_minutes: int
) -> datetime:
    """Return the UTC lock deadline = local kickoff on ``event_date`` minus offset."""
    tz = ZoneInfo(tz_name)
    local_kickoff = datetime.combine(event_date, parse_hhmm(start_time), tzinfo=tz)
    local_lock = local_kickoff - timedelta(minutes=offset_minutes)
    return local_lock.astimezone(timezone.utc)


def due_ping_offsets(
    now: datetime,
    kickoff: datetime,
    offsets: list[int],
    already_sent: set[int],
) -> list[int]:
    """Return offsets whose pre-kickoff ping is now due and not yet sent.

    An offset is due when ``kickoff - offset <= now < kickoff`` (the window has
    opened but kickoff hasn't passed) and it isn't already in ``already_sent``.
    """
    due: list[int] = []
    for offset in offsets:
        if offset in already_sent:
            continue
        ping_time = kickoff - timedelta(minutes=offset)
        if ping_time <= now < kickoff:
            due.append(offset)
    return due


def as_utc(dt: datetime) -> datetime:
    """Coerce a datetime to timezone-aware UTC.

    Naive datetimes (e.g. read back from SQLite) are assumed to already be UTC.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
