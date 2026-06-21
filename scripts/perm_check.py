"""Check the bot's effective permissions in the check-in channel, then exit.

Run with: .venv/bin/python -m scripts.perm_check
"""

from __future__ import annotations

import asyncio

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
    async def _check() -> None:
        guild = bot.get_guild(settings.guild_id)
        channel = bot.get_channel(settings.checkin_channel_id)
        if guild is None or channel is None:
            print("Could not resolve guild or channel.")
        else:
            perms = channel.permissions_for(guild.me)
            print(f"PERMISSION CHECK for #{channel.name} as {bot.user}")
            print(f"  view_channel:     {perms.view_channel}")
            print(f"  send_messages:    {perms.send_messages}")
            print(f"  embed_links:      {perms.embed_links}")
            print(f"  mention_everyone: {perms.mention_everyone}")
            print(f"  administrator:    {perms.administrator}")
        await bot.close()

    try:
        await asyncio.wait_for(bot.start(settings.discord_token), timeout=45)
    except asyncio.TimeoutError:
        print("TIMEOUT")
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
