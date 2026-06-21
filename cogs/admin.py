"""Captain-only slash commands: lock, unlock, event type, reminders."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from bot import checkin_manager
from database.models import EventType
from utils.interactions import ephemeral_then_delete, finish_and_delete
from utils.permissions import is_captain
from utils.time_utils import format_ampm, parse_time_flexible

_NO_EVENT = "There is no check-in for today yet. Use `/checkin` first."


class AdminCog(commands.Cog):
    """Commands restricted to captains (Administrator permission or captain role)."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def _is_captain(self, interaction: discord.Interaction) -> bool:
        member = interaction.user
        return isinstance(member, discord.Member) and is_captain(
            member, self.bot.settings.captain_role_id
        )

    async def _deny(self, interaction: discord.Interaction) -> None:
        await ephemeral_then_delete(
            interaction, "Only captains can use this command."
        )

    @app_commands.command(name="lock", description="Lock today's check-in (captain).")
    async def lock(self, interaction: discord.Interaction) -> None:
        if not self._is_captain(interaction):
            return await self._deny(interaction)
        await interaction.response.defer(ephemeral=True)
        event = await checkin_manager.lock_today(
            self.bot, locked_by=interaction.user.id
        )
        await finish_and_delete(
            interaction, "🔒 Check-in locked." if event else _NO_EVENT
        )

    @app_commands.command(name="unlock", description="Unlock today's check-in (captain).")
    async def unlock(self, interaction: discord.Interaction) -> None:
        if not self._is_captain(interaction):
            return await self._deny(interaction)
        await interaction.response.defer(ephemeral=True)
        event = await checkin_manager.unlock_today(self.bot)
        await finish_and_delete(
            interaction, "🔓 Check-in unlocked." if event else _NO_EVENT
        )

    @app_commands.command(
        name="eventtype", description="Set today's event type (captain)."
    )
    @app_commands.choices(
        event_type=[
            app_commands.Choice(name="Practice", value="practice"),
            app_commands.Choice(name="Match", value="match"),
            app_commands.Choice(name="Tournament", value="tournament"),
            app_commands.Choice(name="League Match", value="league_match"),
            app_commands.Choice(name="Friendly", value="friendly"),
            app_commands.Choice(name="Trials", value="trials"),
        ]
    )
    async def eventtype(
        self,
        interaction: discord.Interaction,
        event_type: app_commands.Choice[str],
    ) -> None:
        if not self._is_captain(interaction):
            return await self._deny(interaction)
        await interaction.response.defer(ephemeral=True)
        event = await checkin_manager.set_today_event_type(
            self.bot, EventType(event_type.value)
        )
        await finish_and_delete(
            interaction,
            f"Event type set to **{event_type.name}**." if event else _NO_EVENT,
        )

    @app_commands.command(
        name="settime", description="Set today's kickoff time (captain)."
    )
    @app_commands.describe(time="Kickoff time, e.g. 7:00 PM, 7pm, or 19:00")
    async def settime(self, interaction: discord.Interaction, time: str) -> None:
        if not self._is_captain(interaction):
            return await self._deny(interaction)
        await interaction.response.defer(ephemeral=True)
        try:
            parsed = parse_time_flexible(time)
        except ValueError:
            return await finish_and_delete(
                interaction,
                "Couldn't read that time. Try `7:00 PM`, `7pm`, or `19:00`.",
            )
        canonical = f"{parsed.hour:02d}:{parsed.minute:02d}"
        event = await checkin_manager.set_today_start_time(self.bot, canonical)
        if event is None:
            return await finish_and_delete(interaction, _NO_EVENT)
        label = self.bot.settings.timezone_label
        lock_time = (
            datetime(2000, 1, 1, parsed.hour, parsed.minute)
            - timedelta(minutes=self.bot.settings.lock_offset_minutes)
        ).time()
        await finish_and_delete(
            interaction,
            f"🕖 Kickoff set to **{format_ampm(parsed)} {label}** — "
            f"responses lock at **{format_ampm(lock_time)} {label}**.",
        )

    @app_commands.command(
        name="ping", description="Ping a group in the check-in channel (captain)."
    )
    @app_commands.describe(
        group="Who to ping", note="Optional message to include with the ping"
    )
    @app_commands.choices(
        group=[
            app_commands.Choice(name="Available players", value="available"),
            app_commands.Choice(name="Everyone", value="everyone"),
            app_commands.Choice(name="No response yet", value="no-response"),
        ]
    )
    async def ping(
        self,
        interaction: discord.Interaction,
        group: app_commands.Choice[str],
        note: Optional[str] = None,
    ) -> None:
        if not self._is_captain(interaction):
            return await self._deny(interaction)
        await interaction.response.defer(ephemeral=True)
        count = await checkin_manager.ping_group(self.bot, group.value, note)
        if count is None:
            message = _NO_EVENT
        elif group.value == "everyone":
            message = "📣 Pinged @everyone."
        elif count == 0:
            message = f"Nobody is in **{group.name}** to ping."
        else:
            message = f"📣 Pinged **{group.name}** ({count})."
        await finish_and_delete(interaction, message)

    @app_commands.command(
        name="remind", description="Remind members who haven't responded (captain)."
    )
    async def remind(self, interaction: discord.Interaction) -> None:
        if not self._is_captain(interaction):
            return await self._deny(interaction)
        await interaction.response.defer(ephemeral=True)
        count = await checkin_manager.send_reminders(self.bot)
        await finish_and_delete(
            interaction,
            f"Reminded {count} member(s)." if count else "Nobody to remind.",
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AdminCog(bot))
