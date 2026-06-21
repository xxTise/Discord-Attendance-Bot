"""Reset today's event after a dry-run: unlock, restore 7 PM kickoff, refresh board.

Run with: .venv/bin/python -m scripts.reset_today  (while main.py is stopped)
"""

from __future__ import annotations

import asyncio

from bot import checkin_manager
from bot.client import CheckInBot
from bot.config import get_settings
from database.base import create_engine_and_sessionmaker
from database.init_db import init_models
from utils.logging_config import configure_logging


async def main() -> None:
    configure_logging()
    settings = get_settings()
    engine, session_factory = create_engine_and_sessionmaker(settings.database_url)
    await init_models(engine)
    bot = CheckInBot(settings, session_factory)

    @bot.listen("on_ready")
    async def _reset() -> None:
        await checkin_manager.unlock_today(bot)
        await checkin_manager.set_today_start_time(bot, settings.event_time)
        print(f"RESET: today unlocked, kickoff restored to {settings.event_time}")
        await bot.close()

    try:
        await asyncio.wait_for(bot.start(settings.discord_token), timeout=45)
    except asyncio.TimeoutError:
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
