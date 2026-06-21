"""Helpers for short-lived (self-deleting) ephemeral interaction replies."""

from __future__ import annotations

import asyncio
import contextlib

import discord

DEFAULT_DELAY = 3.0


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
