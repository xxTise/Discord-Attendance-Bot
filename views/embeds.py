"""Builders that turn event/response data into Discord embeds.

The embed is always rendered from database state, never from in-memory UI state,
so concurrent button clicks cannot desync the displayed board.
"""

from __future__ import annotations

from collections.abc import Sequence
from zoneinfo import ZoneInfo

import discord

from database.models import Event, EventStatus, Response, ResponseState
from utils.time_utils import as_utc, format_ampm, parse_hhmm

_STATE_ORDER = [
    ResponseState.AVAILABLE,
    ResponseState.LATE,
    ResponseState.UNAVAILABLE,
]
_STATE_LABEL = {
    ResponseState.AVAILABLE: "✅ Available",
    ResponseState.LATE: "🕒 Late",
    ResponseState.UNAVAILABLE: "❌ Unavailable",
}


def _format_player(response: Response) -> str:
    name = response.player.display_name
    if response.state is ResponseState.LATE and response.eta:
        return f"{name} — _{response.eta}_"
    return name


def build_checkin_embed(
    event: Event,
    responses: Sequence[Response],
    *,
    tz_name: str = "UTC",
    tz_label: str = "",
) -> discord.Embed:
    """Build the check-in board embed for an event and its responses.

    All times are shown on a 12-hour clock in the configured timezone.
    """
    grouped: dict[ResponseState, list[Response]] = {s: [] for s in _STATE_ORDER}
    for response in responses:
        grouped[response.state].append(response)

    is_locked = event.status is EventStatus.LOCKED
    status_line = "🔒 Locked" if is_locked else "🟢 Open"
    color = discord.Color.greyple() if is_locked else discord.Color.blurple()

    label_suffix = f" {tz_label}".rstrip()
    kickoff = f"{format_ampm(parse_hhmm(event.start_time))}{label_suffix}"

    embed = discord.Embed(
        title=f"📋 Daily Check-In — {event.event_type.label}",
        description=(
            f"**Date:** {event.event_date:%A, %b %d %Y}\n"
            f"🕖 **Kickoff:** {kickoff}\n"
            f"**Status:** {status_line}"
        ),
        color=color,
    )

    for state in _STATE_ORDER:
        members = grouped[state]
        names = "\n".join(_format_player(r) for r in members) if members else "—"
        embed.add_field(
            name=f"{_STATE_LABEL[state]} ({len(members)})",
            value=names,
            inline=False,
        )

    tz = ZoneInfo(tz_name)
    if is_locked and event.locked_at:
        locked_local = as_utc(event.locked_at).astimezone(tz)
        footer = f"Locked at {format_ampm(locked_local.timetz())}{label_suffix}"
    else:
        deadline_local = as_utc(event.lock_deadline).astimezone(tz)
        footer = (
            f"Responses lock at {format_ampm(deadline_local.timetz())}{label_suffix}"
        )
    embed.set_footer(text=footer)
    return embed
