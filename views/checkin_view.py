"""Persistent check-in View with position / Out buttons.

A player marks themselves available by picking exactly one position (GK,
Defense, Midfield, Offense); the Out button marks them unavailable. Picking a
position records an AVAILABLE response carrying that position; clicking another
position replaces the previous pick.

The View carries no per-event state: button ``custom_id``s are stable and the
target event is resolved from the message the buttons are attached to. This lets
``bot.add_view(CheckInView())`` in ``setup_hook`` keep buttons working across
restarts.
"""

from __future__ import annotations

import discord

from database.models import Position, ResponseState


class CheckInView(discord.ui.View):
    """Buttons attached to a daily check-in message."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="GK",
        emoji="🧤",
        style=discord.ButtonStyle.primary,
        custom_id="checkin:gk",
        row=0,
    )
    async def gk(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self._record(interaction, ResponseState.AVAILABLE, Position.GK)

    @discord.ui.button(
        label="Defense",
        emoji="🛡️",
        style=discord.ButtonStyle.primary,
        custom_id="checkin:defense",
        row=0,
    )
    async def defense(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self._record(interaction, ResponseState.AVAILABLE, Position.DEFENSE)

    @discord.ui.button(
        label="Midfield",
        emoji="⚙️",
        style=discord.ButtonStyle.primary,
        custom_id="checkin:midfield",
        row=0,
    )
    async def midfield(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self._record(interaction, ResponseState.AVAILABLE, Position.MIDFIELD)

    @discord.ui.button(
        label="Offense",
        emoji="⚔️",
        style=discord.ButtonStyle.primary,
        custom_id="checkin:offense",
        row=0,
    )
    async def offense(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self._record(interaction, ResponseState.AVAILABLE, Position.OFFENSE)

    @discord.ui.button(
        label="Out",
        emoji="❌",
        style=discord.ButtonStyle.danger,
        custom_id="checkin:unavailable",
        row=1,
    )
    async def unavailable(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self._record(interaction, ResponseState.UNAVAILABLE, None)

    async def _record(
        self,
        interaction: discord.Interaction,
        state: ResponseState,
        position: Position | None,
    ) -> None:
        # Imported lazily to avoid a circular import at module load time.
        from bot.checkin_manager import apply_response

        await apply_response(
            interaction.client,
            interaction,
            state=state,
            position=position,
            eta=None,
            message_id=interaction.message.id,
            channel_id=interaction.channel_id,
        )
