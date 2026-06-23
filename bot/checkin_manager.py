"""Application-level orchestration for check-ins.

This is the bridge between Discord (``discord.py`` objects, channels, messages)
and the pure ``event_service`` rules. Cogs and scheduled jobs call into here so
the posting / refreshing / locking / reminding logic lives in one place.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import discord
from sqlalchemy import select

from database.models import Event, EventStatus, EventType, ResponseState
from services import event_service
from services.errors import EventLockedError, ResponseValidationError
from utils.interactions import ephemeral_then_delete
from utils.time_utils import (
    as_utc,
    at_local_time_utc,
    due_ping_offsets,
    lock_deadline_from_kickoff,
    today_in_tz,
    utcnow,
)
from views.embeds import build_checkin_embed

log = logging.getLogger("proclubs.checkin")


async def _get_channel(bot: discord.Client, channel_id: int) -> Optional[discord.abc.Messageable]:
    channel = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except discord.HTTPException:
            log.warning("Could not resolve channel %s", channel_id)
            return None
    return channel


def _render_embed(bot: discord.Client, event: Event, responses) -> discord.Embed:
    """Build the branded check-in embed using the bot's configured settings."""
    s = bot.settings
    return build_checkin_embed(
        event,
        responses,
        tz_name=s.timezone,
        tz_label=s.timezone_label,
        brand_name=s.brand_name,
        footer_name=s.footer_name,
        squad_size=s.squad_size,
        brand_icon_url=(s.brand_icon_url or None),
    )


async def _fetch_message(
    bot: discord.Client, channel_id: Optional[int], message_id: Optional[int]
) -> Optional[discord.Message]:
    """Return the stored check-in message, or None if it's gone/unreachable."""
    if not channel_id or not message_id:
        return None
    channel = await _get_channel(bot, channel_id)
    if channel is None:
        return None
    try:
        return await channel.fetch_message(message_id)
    except discord.NotFound:
        return None
    except discord.HTTPException:
        log.warning("Could not fetch message %s", message_id)
        return None


async def refresh_checkin_message(
    bot: discord.Client, message_id: int, channel_id: int
) -> None:
    """Re-render the check-in embed from the database and edit the message.

    When the event is locked the buttons are removed so it becomes read-only.
    """
    from views.checkin_view import CheckInView

    async with bot.session_factory() as session:
        event = await event_service.get_event_by_message_id(session, message_id)
        if event is None:
            return
        responses = await event_service.list_responses(session, event)
        embed = _render_embed(bot, event, responses)
        is_locked = event.status is EventStatus.LOCKED

    channel = await _get_channel(bot, channel_id)
    if channel is None:
        return
    try:
        message = await channel.fetch_message(message_id)
    except discord.NotFound:
        log.warning("Check-in message %s no longer exists", message_id)
        return
    view = None if is_locked else CheckInView()
    await message.edit(embed=embed, view=view)


async def apply_response(
    bot: discord.Client,
    interaction: discord.Interaction,
    *,
    state: ResponseState,
    eta: Optional[str],
    message_id: int,
    channel_id: int,
) -> None:
    """Record a button/modal response and refresh the public board.

    Always replies to the interaction ephemerally; refreshes the shared message
    only on success.
    """
    user = interaction.user
    async with bot.session_factory() as session:
        event = await event_service.get_event_by_message_id(session, message_id)
        if event is None:
            await ephemeral_then_delete(
                interaction, "This check-in is no longer active."
            )
            return
        try:
            await event_service.set_response(
                session,
                event,
                discord_id=user.id,
                display_name=user.display_name,
                state=state,
                eta=eta,
            )
        except (EventLockedError, ResponseValidationError) as exc:
            await ephemeral_then_delete(interaction, str(exc))
            return
        await session.commit()

    log.info("Recorded %s for %s on message %s", state.value, user.id, message_id)
    # Silently acknowledge — the refreshed board is the confirmation.
    if not interaction.response.is_done():
        await interaction.response.defer()
    try:
        await refresh_checkin_message(bot, message_id, channel_id)
    except discord.HTTPException:
        log.exception("Failed to refresh check-in message %s", message_id)


async def post_daily_checkin(
    bot: discord.Client,
    *,
    channel_id: int,
    default_type: EventType = EventType.PRACTICE,
) -> tuple[Optional[Event], bool]:
    """Create (if needed) and post today's check-in.

    Returns ``(event, created)`` where ``created`` is False if today's check-in
    was already posted.
    """
    from views.checkin_view import CheckInView

    tz = bot.settings.timezone
    event_date = today_in_tz(tz)
    lock_deadline = lock_deadline_from_kickoff(
        event_date, bot.settings.event_time, tz, bot.settings.lock_offset_minutes
    )

    async with bot.session_factory() as session:
        event = await event_service.get_or_create_event(
            session,
            event_date=event_date,
            lock_deadline=lock_deadline,
            start_time=bot.settings.event_time,
            channel_id=channel_id,
            default_type=default_type,
        )
        responses = await event_service.list_responses(session, event)
        embed = _render_embed(bot, event, responses)

        # If we already posted today and that message still exists, just refresh it.
        existing = await _fetch_message(bot, event.channel_id, event.message_id)
        if existing is not None:
            view = None if event.status is EventStatus.LOCKED else CheckInView()
            await existing.edit(embed=embed, view=view)
            await session.commit()
            return event, False

        # Never posted, or the old message was deleted — (re)post a fresh one.
        channel = await _get_channel(bot, channel_id)
        if channel is None:
            await session.commit()
            return None, False
        message = await channel.send(
            content="@everyone **roster call is live** — lock in below. 🎮",
            embed=embed,
            view=CheckInView(),
            allowed_mentions=discord.AllowedMentions(everyone=True),
        )
        event.message_id = message.id
        event.channel_id = channel_id
        await session.commit()

    log.info("Posted check-in for %s (message %s)", event_date, event.message_id)
    return event, True


async def lock_today(
    bot: discord.Client, *, locked_by: Optional[int] = None
) -> Optional[Event]:
    """Lock today's check-in. Returns the event, or None if none exists."""
    return await _set_today_locked(bot, locked=True, locked_by=locked_by)


async def unlock_today(bot: discord.Client) -> Optional[Event]:
    """Unlock today's check-in. Returns the event, or None if none exists."""
    return await _set_today_locked(bot, locked=False, locked_by=None)


async def _set_today_locked(
    bot: discord.Client, *, locked: bool, locked_by: Optional[int]
) -> Optional[Event]:
    event_date = today_in_tz(bot.settings.timezone)
    async with bot.session_factory() as session:
        event = await event_service.get_event_by_date(session, event_date)
        if event is None:
            return None
        if locked:
            await event_service.lock_event(session, event, locked_by=locked_by)
        else:
            await event_service.unlock_event(session, event)
        await session.commit()
        message_id, channel_id = event.message_id, event.channel_id
    if message_id and channel_id:
        await refresh_checkin_message(bot, message_id, channel_id)
    return event


async def set_today_event_type(
    bot: discord.Client, event_type: EventType
) -> Optional[Event]:
    """Change today's event type. Returns the event, or None if none exists."""
    event_date = today_in_tz(bot.settings.timezone)
    async with bot.session_factory() as session:
        event = await event_service.get_event_by_date(session, event_date)
        if event is None:
            return None
        await event_service.set_event_type(session, event, event_type)
        await session.commit()
        message_id, channel_id = event.message_id, event.channel_id
    if message_id and channel_id:
        await refresh_checkin_message(bot, message_id, channel_id)
    return event


async def set_today_start_time(
    bot: discord.Client, start_time: str
) -> Optional[Event]:
    """Set today's kickoff time (``"HH:MM"``), moving the lock deadline with it.

    Returns the event, or None.
    """
    tz = bot.settings.timezone
    event_date = today_in_tz(tz)
    lock_deadline = lock_deadline_from_kickoff(
        event_date, start_time, tz, bot.settings.lock_offset_minutes
    )
    async with bot.session_factory() as session:
        event = await event_service.get_event_by_date(session, event_date)
        if event is None:
            return None
        await event_service.set_event_start_time(
            session, event, start_time, lock_deadline=lock_deadline
        )
        await session.commit()
        message_id, channel_id = event.message_id, event.channel_id
    if message_id and channel_id:
        await refresh_checkin_message(bot, message_id, channel_id)
    return event


async def auto_lock_due_events(bot: discord.Client) -> int:
    """Lock any open events whose deadline has passed. Returns the number locked."""
    now = utcnow()
    locked: list[tuple[int, int]] = []
    async with bot.session_factory() as session:
        open_events = await session.scalars(
            select(Event).where(Event.status == EventStatus.OPEN)
        )
        for event in open_events:
            if event.message_id and as_utc(event.lock_deadline) <= now:
                await event_service.lock_event(session, event)
                locked.append((event.message_id, event.channel_id))
        if locked:
            await session.commit()

    for message_id, channel_id in locked:
        try:
            await refresh_checkin_message(bot, message_id, channel_id)
        except discord.HTTPException:
            log.exception("Failed to refresh locked message %s", message_id)
    if locked:
        log.info("Auto-locked %d event(s)", len(locked))
    return len(locked)


async def ping_group(
    bot: discord.Client, target: str, note: Optional[str] = None
) -> Optional[int]:
    """Post a channel mention for a group of members.

    ``target`` is one of ``"available"``, ``"everyone"``, or ``"no-response"``.
    Returns the number of members pinged, 0 if the group is empty, or None if the
    action needs today's check-in and none exists (or the channel is unreachable).
    """
    tz = bot.settings.timezone
    guild = bot.get_guild(bot.settings.guild_id)
    channel_id = bot.settings.checkin_channel_id

    if target == "everyone":
        content = "@everyone"
        allowed = discord.AllowedMentions(everyone=True)
        count = len([m for m in guild.members if not m.bot]) if guild else 0
    else:
        async with bot.session_factory() as session:
            event = await event_service.get_event_by_date(session, today_in_tz(tz))
            if event is None:
                return None
            if event.channel_id:
                channel_id = event.channel_id
            if target == "available":
                responses = await event_service.list_responses(session, event)
                ids = [
                    r.player.discord_id
                    for r in responses
                    if r.state is ResponseState.AVAILABLE
                ]
            else:  # no-response
                member_ids = (
                    [m.id for m in guild.members if not m.bot] if guild else []
                )
                ids = await event_service.get_non_responders(
                    session, event, member_ids
                )
        if not ids:
            return 0
        content = " ".join(f"<@{uid}>" for uid in ids)
        allowed = discord.AllowedMentions(users=True)
        count = len(ids)

    if note:
        content = f"{content}\n{note}"
    channel = await _get_channel(bot, channel_id)
    if channel is None:
        return None
    await channel.send(content, allowed_mentions=allowed)
    log.info("Pinged group '%s' (%s member(s))", target, count)
    return count


@dataclass(frozen=True)
class PreKickoffPing:
    """One scheduled pre-kickoff announcement."""

    offset_minutes: int  # minutes before kickoff to fire
    target: str  # "everyone", "available", or "no-response"
    message: str


# Fired automatically by the every-minute scheduler, relative to each event's
# kickoff (so they track changes made via /settime).
PREKICKOFF_SCHEDULE: list[PreKickoffPing] = [
    PreKickoffPing(
        offset_minutes=75,
        target="no-response",
        message=(
            "⚠️ **The check-in locks in 15 minutes!** If you haven't marked your "
            "availability yet, do it now — once it's locked you won't be able to "
            "set your status."
        ),
    ),
    PreKickoffPing(
        offset_minutes=60,
        target="everyone",
        message=(
            "🔒 **Availability is now locked.** If your availability has changed, "
            "please contact a captain directly to let them know your status."
        ),
    ),
    PreKickoffPing(
        offset_minutes=30,
        target="available",
        message=(
            "⏰ **30 minutes until kickoff** — start getting ready to lobby up!"
        ),
    ),
]


async def run_prekickoff_pings(bot: discord.Client) -> list[int]:
    """Fire any scheduled pre-kickoff pings whose window has opened.

    Called every minute. Marks offsets as sent before pinging so an overlapping
    run can't double-post. Returns the offsets that fired this run.
    """
    if not PREKICKOFF_SCHEDULE:
        return []

    tz = bot.settings.timezone
    event_date = today_in_tz(tz)
    now = utcnow()
    offsets = [p.offset_minutes for p in PREKICKOFF_SCHEDULE]

    async with bot.session_factory() as session:
        event = await event_service.get_event_by_date(session, event_date)
        if event is None:
            return []
        kickoff_utc = at_local_time_utc(event_date, event.start_time, tz)
        already = {
            int(part) for part in (event.pinged_offsets or "").split(",") if part.strip()
        }
        due = due_ping_offsets(now, kickoff_utc, offsets, already)
        if not due:
            return []
        event.pinged_offsets = ",".join(str(o) for o in sorted(already | set(due)))
        await session.commit()

    by_offset = {p.offset_minutes: p for p in PREKICKOFF_SCHEDULE}
    for offset in due:
        entry = by_offset[offset]
        try:
            await ping_group(bot, entry.target, entry.message)
        except discord.HTTPException:
            log.exception("Pre-kickoff ping failed for offset %s", offset)
    log.info("Fired pre-kickoff pings: %s", due)
    return due


async def send_reminders(bot: discord.Client, *, use_dm: bool = True) -> int:
    """Ping members who have not responded to today's open check-in.

    Tries a DM first; members with DMs disabled are collected and mentioned in
    the check-in channel instead. Returns the number of members reminded.
    """
    tz = bot.settings.timezone
    event_date = today_in_tz(tz)
    guild = bot.get_guild(bot.settings.guild_id)
    if guild is None:
        log.warning("Guild %s not available for reminders", bot.settings.guild_id)
        return 0

    member_ids = [m.id for m in guild.members if not m.bot]
    async with bot.session_factory() as session:
        event = await event_service.get_event_by_date(session, event_date)
        if event is None or event.status is EventStatus.LOCKED:
            return 0
        non_responders = await event_service.get_non_responders(
            session, event, member_ids
        )
        channel_id = event.channel_id

    if not non_responders:
        return 0

    dm_failed: list[int] = []
    if use_dm:
        for user_id in non_responders:
            member = guild.get_member(user_id)
            if member is None:
                continue
            try:
                await member.send(
                    "⏰ Reminder: you haven't responded to today's Pro Clubs "
                    "check-in yet. Please mark your availability."
                )
            except discord.Forbidden:
                dm_failed.append(user_id)
            except discord.HTTPException:
                log.exception("DM reminder failed for %s", user_id)
                dm_failed.append(user_id)

    fallback = dm_failed if use_dm else non_responders
    if fallback and channel_id:
        channel = await _get_channel(bot, channel_id)
        if channel is not None:
            mentions = " ".join(f"<@{uid}>" for uid in fallback)
            await channel.send(
                f"⏰ Reminder — please respond to today's check-in: {mentions}"
            )

    log.info("Sent reminders to %d member(s)", len(non_responders))
    return len(non_responders)
