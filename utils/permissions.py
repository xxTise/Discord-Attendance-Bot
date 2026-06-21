"""Authorization helpers for captain-only actions."""

from __future__ import annotations

import discord


def is_captain(member: discord.Member, captain_role_id: int) -> bool:
    """Return True if the member may run captain commands.

    A captain is anyone with the Discord Administrator permission, or anyone
    holding the configured captain role (when ``captain_role_id`` is set).
    """
    if member.guild_permissions.administrator:
        return True
    if captain_role_id and any(role.id == captain_role_id for role in member.roles):
        return True
    return False
