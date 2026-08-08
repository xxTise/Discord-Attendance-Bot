"""Application-level orchestration for the weekly attendance analytics report.

Bridges the pure Athena query (``services.analytics_service``) and Discord
posting, mirroring ``bot.checkin_manager``'s service/Discord separation.
"""

from __future__ import annotations

import logging

import discord

from services import analytics_service
from services.analytics_service import AthenaQueryError
from utils.interactions import resolve_channel
from views.embeds import build_analytics_embed

log = logging.getLogger("proclubs.analytics")


async def post_weekly_report(bot: discord.Client) -> None:
    """Run the attendance report and post it to the configured channel."""
    settings = bot.settings
    if not settings.analytics_channel_id:
        log.warning("ANALYTICS_CHANNEL_ID not set; skipping weekly report")
        return

    channel = await resolve_channel(bot, settings.analytics_channel_id)
    if channel is None:
        return

    try:
        rows = await analytics_service.fetch_attendance_report(
            region=settings.aws_region,
            database=settings.athena_database,
            output_location=settings.athena_output_s3,
        )
    except AthenaQueryError as exc:
        log.error("Weekly analytics report failed: %s", exc)
        return

    embed = build_analytics_embed(
        rows,
        brand_name=settings.brand_name,
        brand_icon_url=settings.brand_icon_url or None,
    )
    await channel.send(embed=embed)
    log.info("Posted weekly analytics report (%d players)", len(rows))
