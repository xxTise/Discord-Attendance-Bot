"""APScheduler setup for daily posting, auto-locking, and reminders."""

from __future__ import annotations

import logging
from zoneinfo import ZoneInfo

import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from scheduler import jobs
from utils.time_utils import parse_hhmm

log = logging.getLogger("proclubs.scheduler")


def create_scheduler(bot: discord.Client) -> AsyncIOScheduler:
    """Create and configure (but do not start) the scheduler for ``bot``."""
    tz = ZoneInfo(bot.settings.timezone)
    scheduler = AsyncIOScheduler(timezone=tz)

    checkin = parse_hhmm(bot.settings.checkin_time)
    scheduler.add_job(
        jobs.daily_checkin_job,
        CronTrigger(hour=checkin.hour, minute=checkin.minute, timezone=tz),
        args=[bot],
        id="daily_checkin",
        replace_existing=True,
    )

    # Auto-lock runs on a short interval so a missed cron tick (bot offline at the
    # deadline) still locks the event on the next sweep.
    scheduler.add_job(
        jobs.auto_lock_job,
        IntervalTrigger(minutes=1),
        args=[bot],
        id="auto_lock",
        replace_existing=True,
    )

    # Pre-kickoff pings are kickoff-relative (and kickoff can change via /settime),
    # so they're evaluated on the same short interval rather than a fixed cron.
    scheduler.add_job(
        jobs.prekickoff_ping_job,
        IntervalTrigger(minutes=1),
        args=[bot],
        id="prekickoff_ping",
        replace_existing=True,
    )

    log.info(
        "Scheduler configured: check-in %s, auto-lock + pre-kickoff pings every 1m (%s)",
        bot.settings.checkin_time,
        bot.settings.timezone,
    )
    return scheduler
