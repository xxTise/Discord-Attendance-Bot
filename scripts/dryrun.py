"""Time-compressed live dry-run of the pre-kickoff pings.

Stops nothing itself — run this only while main.py is NOT running (single login).
It reuses the real ping messages/targets but fires them 3 and 2 minutes before a
kickoff set ~4 minutes out, so the whole sequence plays in a few minutes.

Run with: .venv/bin/python -m scripts.dryrun
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from zoneinfo import ZoneInfo

from bot import checkin_manager
from bot.checkin_manager import PreKickoffPing
from bot.client import CheckInBot
from bot.config import get_settings
from database.base import create_engine_and_sessionmaker
from database.init_db import init_models
from utils.logging_config import configure_logging
from utils.time_utils import utcnow

RUN_SECONDS = 210


async def main() -> None:
    configure_logging()
    settings = get_settings()
    engine, session_factory = create_engine_and_sessionmaker(settings.database_url)
    await init_models(engine)
    bot = CheckInBot(settings, session_factory)

    # Speed up: fire 3 and 2 minutes before kickoff, reusing real targets/messages.
    real = {p.offset_minutes: p for p in checkin_manager.PREKICKOFF_SCHEDULE}
    checkin_manager.PREKICKOFF_SCHEDULE = [
        PreKickoffPing(3, real[60].target, real[60].message),
        PreKickoffPing(2, real[30].target, real[30].message),
    ]

    @bot.listen("on_ready")
    async def _go() -> None:
        tz = ZoneInfo(settings.timezone)
        await checkin_manager.post_daily_checkin(
            bot, channel_id=settings.checkin_channel_id
        )
        kickoff_local = utcnow().astimezone(tz) + timedelta(minutes=4)
        hhmm = f"{kickoff_local.hour:02d}:{kickoff_local.minute:02d}"
        await checkin_manager.set_today_start_time(bot, hhmm)
        print(f"DRYRUN: kickoff set to {hhmm} {settings.timezone_label}")
        print("DRYRUN: expect board LOCK ~1m, @everyone announcement ~2m, "
              "lobby-up ping ~3m. Watch #availability.")

    try:
        await asyncio.wait_for(bot.start(settings.discord_token), timeout=RUN_SECONDS)
    except asyncio.TimeoutError:
        pass
    finally:
        if not bot.is_closed():
            await bot.close()
    print("DRYRUN: finished.")


if __name__ == "__main__":
    asyncio.run(main())
