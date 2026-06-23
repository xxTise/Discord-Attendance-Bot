"""Builders that turn event/response data into a premium check-in embed.

The embed is always rendered from database state, never from in-memory UI state,
so concurrent button clicks cannot desync the displayed board. The squad bar
"fills" because the board is re-rendered on every Available click.
"""

from __future__ import annotations

from collections.abc import Sequence
from zoneinfo import ZoneInfo

import discord

from database.models import Event, EventStatus, Response, ResponseState
from utils.time_utils import as_utc, at_local_time_utc, format_ampm, parse_hhmm

# Only these states render. Legacy LATE rows (Late was removed) are ignored.
_STATE_ORDER = [ResponseState.AVAILABLE, ResponseState.UNAVAILABLE]

_OPEN_COLOR = discord.Color(0x57F287)   # Discord green
_LOCKED_COLOR = discord.Color(0x80848E)  # muted grey

_BAR_FILLED = "🟩"
_BAR_EMPTY = "⬜"


def _progress_bar(available: int, squad_size: int) -> str:
    """Render the squad availability bar: one green block per Available player."""
    filled = max(0, min(available, squad_size))
    bar = _BAR_FILLED * filled + _BAR_EMPTY * (squad_size - filled)
    if available >= squad_size and squad_size > 0:
        return f"{bar}\n**{available}/{squad_size}** · 🔥 **FULL SQUAD LOCKED IN**"
    return f"{bar}\n**{available}/{squad_size}** locked in"


def _names(responses: list[Response]) -> str:
    return " · ".join(r.player.display_name for r in responses) or "—"


def build_checkin_embed(
    event: Event,
    responses: Sequence[Response],
    *,
    tz_name: str = "UTC",
    tz_label: str = "",
    brand_name: str = "",
    footer_name: str = "",
    squad_size: int = 11,
    brand_icon_url: str | None = None,
) -> discord.Embed:
    """Build the premium check-in board embed for an event and its responses."""
    grouped: dict[ResponseState, list[Response]] = {s: [] for s in _STATE_ORDER}
    for response in responses:
        if response.state in grouped:
            grouped[response.state].append(response)
    available = grouped[ResponseState.AVAILABLE]
    out = grouped[ResponseState.UNAVAILABLE]

    is_locked = event.status is EventStatus.LOCKED
    suffix = f" {tz_label}".rstrip()
    tz = ZoneInfo(tz_name)

    embed = discord.Embed(
        title=f"🎮 Daily Check-In — {event.event_type.label}",
        color=_LOCKED_COLOR if is_locked else _OPEN_COLOR,
    )
    if brand_name:
        embed.set_author(name=brand_name, icon_url=brand_icon_url)

    # Top row: Date · Kickoff (with live relative time) · Status
    kickoff_unix = int(at_local_time_utc(event.event_date, event.start_time, tz_name).timestamp())
    kickoff_str = f"{format_ampm(parse_hhmm(event.start_time))}{suffix}"
    embed.add_field(name="📅 Date", value=f"**{event.event_date:%a, %b %d}**", inline=True)
    embed.add_field(
        name="🚀 Kickoff", value=f"**{kickoff_str}**\n<t:{kickoff_unix}:R>", inline=True
    )
    embed.add_field(
        name="📊 Status",
        value="🔒 **Locked**" if is_locked else "🟢 **Open**",
        inline=True,
    )

    # Squad availability bar
    embed.add_field(
        name="📋 Squad Availability",
        value=_progress_bar(len(available), squad_size),
        inline=False,
    )

    # Rosters
    embed.add_field(name=f"✅ Available — {len(available)}", value=_names(available), inline=False)
    embed.add_field(name=f"❌ Out — {len(out)}", value=_names(out), inline=False)

    # Footer: brand + lock time
    if is_locked and event.locked_at:
        lock_txt = f"Locked at {format_ampm(as_utc(event.locked_at).astimezone(tz).timetz())}{suffix}"
    else:
        lock_txt = f"Locks at {format_ampm(as_utc(event.lock_deadline).astimezone(tz).timetz())}{suffix}"
    footer_text = f"{footer_name} · {lock_txt}" if footer_name else lock_txt
    embed.set_footer(text=footer_text, icon_url=brand_icon_url)
    return embed
