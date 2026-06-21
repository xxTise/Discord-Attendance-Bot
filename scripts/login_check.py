"""One-shot connectivity check: log in, report guild/channel, then disconnect.

Run with: .venv/bin/python -m scripts.login_check
Does not post anything; it only verifies token, intents, and command sync.
"""

from __future__ import annotations

import asyncio

import discord

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
    async def _report() -> None:
        guild = bot.get_guild(settings.guild_id)
        channel = bot.get_channel(settings.checkin_channel_id)
        print(f"LOGIN OK as {bot.user}")
        print(f"  guild:   {guild.name if guild else 'NOT FOUND'} ({settings.guild_id})")
        print(
            f"  channel: {getattr(channel, 'name', 'NOT FOUND')} "
            f"({settings.checkin_channel_id})"
        )
        print(f"  members cached: {guild.member_count if guild else 'n/a'}")
        cmds = await bot.tree.fetch_commands(guild=discord.Object(id=settings.guild_id))
        print(f"  synced commands: {sorted(c.name for c in cmds)}")
        await bot.close()

    try:
        await asyncio.wait_for(bot.start(settings.discord_token), timeout=45)
    except asyncio.TimeoutError:
        print("TIMEOUT: never reached on_ready")
        await bot.close()
    except discord.PrivilegedIntentsRequired:
        print(
            "PRIVILEGED INTENTS REQUIRED: enable 'Server Members Intent' in the "
            "Discord Developer Portal (Bot tab) for this application."
        )
        await bot.close()
    except discord.LoginFailure as exc:
        print(f"LOGIN FAILED: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
