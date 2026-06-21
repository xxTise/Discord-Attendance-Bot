"""The Discord bot client: lifecycle, persistent views, command sync, scheduler."""

from __future__ import annotations

import logging

import discord
from discord.ext import commands

from bot.config import Settings
from scheduler.scheduler import create_scheduler
from views.checkin_view import CheckInView

log = logging.getLogger("proclubs.client")

_EXTENSIONS = ["cogs.checkin", "cogs.admin"]


class CheckInBot(commands.Bot):
    """Bot with the session factory, settings, and scheduler attached."""

    def __init__(self, settings: Settings, session_factory) -> None:
        intents = discord.Intents.default()
        intents.members = True  # required to list non-responders for reminders
        super().__init__(command_prefix="!", intents=intents)
        self.settings = settings
        self.session_factory = session_factory
        self.scheduler = None

    async def setup_hook(self) -> None:
        # Register the persistent view so buttons survive restarts.
        self.add_view(CheckInView())

        for extension in _EXTENSIONS:
            await self.load_extension(extension)

        guild = discord.Object(id=self.settings.guild_id)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        log.info("Synced application commands to guild %s", self.settings.guild_id)

        self.scheduler = create_scheduler(self)
        self.scheduler.start()

    async def on_ready(self) -> None:
        log.info("Logged in as %s (id=%s)", self.user, self.user.id)

    async def close(self) -> None:
        if self.scheduler is not None and self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        await super().close()
