"""Application configuration loaded from environment / .env."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the bot.

    Environment variable names are matched case-insensitively, so ``DISCORD_TOKEN``
    populates :attr:`discord_token`.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    discord_token: str = ""
    guild_id: int = 0
    checkin_channel_id: int = 0
    # Captain actions (lock/unlock, change event type) require either this role
    # or the Discord Administrator permission. 0 disables the role check.
    captain_role_id: int = 0

    timezone: str = "America/Chicago"
    timezone_label: str = "CT"  # short label shown in posts
    checkin_time: str = "12:00"
    event_time: str = "19:00"  # default kickoff time (7:00 PM CT)
    lock_offset_minutes: int = 60  # responses lock this many minutes before kickoff

    # Branding / premium board
    brand_name: str = "PRO CLUBS · MATCHDAY OPS"  # embed author line
    footer_name: str = "Pro Clubs Check-In"  # embed footer label
    brand_icon_url: str = ""  # optional small icon URL for author/footer
    squad_size: int = 11  # Available count that fills the squad bar

    database_url: str = "sqlite+aiosqlite:///./proclubs.db"


@lru_cache
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance."""
    return Settings()
