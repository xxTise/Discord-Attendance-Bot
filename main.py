"""Entry point: initialize the database and run the bot."""

from __future__ import annotations

import asyncio

from bot.client import CheckInBot
from bot.config import get_settings
from database.base import create_engine_and_sessionmaker
from database.init_db import init_models
from utils.logging_config import configure_logging


async def main() -> None:
    log = configure_logging()
    settings = get_settings()

    if not settings.discord_token:
        raise SystemExit("DISCORD_TOKEN is not set. Copy .env.example to .env.")

    engine, session_factory = create_engine_and_sessionmaker(settings.database_url)
    await init_models(engine)
    log.info("Database ready at %s", settings.database_url)

    bot = CheckInBot(settings, session_factory)
    async with bot:
        await bot.start(settings.discord_token)


if __name__ == "__main__":
    asyncio.run(main())
