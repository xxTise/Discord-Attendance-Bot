"""Helpers for short-lived (self-deleting) ephemeral interaction replies."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Optional

import discord

log = logging.getLogger("proclubs.interactions")

DEFAULT_DELAY = 3.0


async def resolve_channel(
    bot: discord.Client, channel_id: int
) -> Optional[discord.abc.Messageable]:
    """Look up a channel by ID, falling back to an API fetch if uncached."""
    channel = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except discord.HTTPException:
            log.warning("Could not resolve channel %s", channel_id)
            return None
    return channel


async def ephemeral_then_delete(
    interaction: discord.Interaction, content: str, *, delay: float = DEFAULT_DELAY
) -> None:
    """Send an ephemeral reply, then delete it after ``delay`` seconds.

    Works whether or not the interaction has already been responded to/deferred.
    """
    if interaction.response.is_done():
        message = await interaction.followup.send(content, ephemeral=True)
        await asyncio.sleep(delay)
        with contextlib.suppress(discord.HTTPException):
            await message.delete()
    else:
        await interaction.response.send_message(content, ephemeral=True)
        await asyncio.sleep(delay)
        with contextlib.suppress(discord.HTTPException):
            await interaction.delete_original_response()


async def finish_and_delete(
    interaction: discord.Interaction, content: str, *, delay: float = DEFAULT_DELAY
) -> None:
    """Fill a previously-deferred ephemeral reply, then delete it after ``delay``."""
    await interaction.edit_original_response(content=content)
    await asyncio.sleep(delay)
    with contextlib.suppress(discord.HTTPException):
        await interaction.delete_original_response()
