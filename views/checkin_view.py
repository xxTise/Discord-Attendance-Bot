"""Persistent check-in View with Available / Unavailable / Late buttons.

The View carries no per-event state: button ``custom_id``s are stable and the
target event is resolved from the message the buttons are attached to. This lets
``bot.add_view(CheckInView())`` in ``setup_hook`` keep buttons working across
restarts.
"""

from __future__ import annotations

import discord

from database.models import ResponseState
from views.late_modal import LateModal


class CheckInView(discord.ui.View):
    """Buttons attached to a daily check-in message."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Available",
        style=discord.ButtonStyle.success,
        custom_id="checkin:available",
    )
    async def available(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self._record(interaction, ResponseState.AVAILABLE)

    @discord.ui.button(
        label="Unavailable",
        style=discord.ButtonStyle.danger,
        custom_id="checkin:unavailable",
    )
    async def unavailable(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self._record(interaction, ResponseState.UNAVAILABLE)

    @discord.ui.button(
        label="Late",
        style=discord.ButtonStyle.secondary,
        custom_id="checkin:late",
    )
    async def late(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.send_modal(
            LateModal(
                message_id=interaction.message.id,
                channel_id=interaction.channel_id,
            )
        )

    async def _record(
        self, interaction: discord.Interaction, state: ResponseState
    ) -> None:
        # Imported lazily to avoid a circular import at module load time.
        from bot.checkin_manager import apply_response

        await apply_response(
            interaction.client,
            interaction,
            state=state,
            eta=None,
            message_id=interaction.message.id,
            channel_id=interaction.channel_id,
        )
