"""Modal that captures an ETA for a Late response."""

from __future__ import annotations

import discord

from database.models import ResponseState


class LateModal(discord.ui.Modal, title="Late — what's your ETA?"):
    """Collects a free-text ETA, then records a Late response."""

    eta: discord.ui.TextInput = discord.ui.TextInput(
        label="ETA",
        placeholder="e.g. 15 min, 8:30, after work",
        max_length=100,
        required=True,
    )

    def __init__(self, *, message_id: int, channel_id: int) -> None:
        super().__init__()
        self._message_id = message_id
        self._channel_id = channel_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        # Imported lazily to avoid a circular import at module load time.
        from bot.checkin_manager import apply_response

        await apply_response(
            interaction.client,
            interaction,
            state=ResponseState.LATE,
            eta=str(self.eta),
            message_id=self._message_id,
            channel_id=self._channel_id,
        )
