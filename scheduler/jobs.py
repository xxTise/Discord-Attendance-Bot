"""Scheduled job functions. Thin wrappers over the check-in manager."""

from __future__ import annotations

import logging

import discord

from bot import checkin_manager

log = logging.getLogger("proclubs.jobs")


async def daily_checkin_job(bot: discord.Client) -> None:
    """Post the daily check-in at the configured time."""
    await checkin_manager.post_daily_checkin(
        bot, channel_id=bot.settings.checkin_channel_id
    )


async def auto_lock_job(bot: discord.Client) -> None:
    """Lock any open events past their deadline."""
    await checkin_manager.auto_lock_due_events(bot)


async def prekickoff_ping_job(bot: discord.Client) -> None:
    """Fire automatic pings at the configured minutes before kickoff."""
    await checkin_manager.run_prekickoff_pings(bot)
