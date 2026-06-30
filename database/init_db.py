"""Database initialization helpers."""

from __future__ import annotations

from sqlalchemy import Connection

from sqlalchemy.ext.asyncio import AsyncEngine

from database import models  # noqa: F401  (ensures models register on Base.metadata)
from database.base import Base


def _ensure_columns(conn: Connection) -> None:
    """Lightweight forward-only migrations for SQLite (pre-Alembic).

    Adds columns introduced after a table was first created. Idempotent.
    """
    events = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(events)")}
    if "start_time" not in events:
        conn.exec_driver_sql(
            "ALTER TABLE events ADD COLUMN start_time VARCHAR(5) "
            "NOT NULL DEFAULT '19:00'"
        )
    if "pinged_offsets" not in events:
        conn.exec_driver_sql(
            "ALTER TABLE events ADD COLUMN pinged_offsets VARCHAR(50) "
            "NOT NULL DEFAULT ''"
        )

    responses = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(responses)")}
    if responses and "position" not in responses:
        # Nullable: existing rows (and all UNAVAILABLE rows) keep a NULL position.
        conn.exec_driver_sql("ALTER TABLE responses ADD COLUMN position VARCHAR(9)")


async def init_models(engine: AsyncEngine) -> None:
    """Create all tables that do not yet exist and apply column migrations."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_ensure_columns)
