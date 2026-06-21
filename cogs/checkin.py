"""Slash commands for posting the daily check-in."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from bot import checkin_manager
from utils.interactions import finish_and_delete


class CheckInCog(commands.Cog):
    """Player-facing check-in commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="checkin", description="Post today's check-in (or confirm it's posted)."
    )
    async def checkin(self, interaction: discord.Interaction) -> None:
        """Manually post today's check-in to the configured channel."""
        await interaction.response.defer(ephemeral=True)
        _, created = await checkin_manager.post_daily_checkin(
            self.bot, channel_id=self.bot.settings.checkin_channel_id
        )
        message = (
            "Posted today's check-in."
            if created
            else "Today's check-in is already posted."
        )
        await finish_and_delete(interaction, message)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CheckInCog(bot))
