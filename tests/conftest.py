"""Shared test fixtures: an in-memory async SQLite database per test."""

from __future__ import annotations

import pytest_asyncio
from sqlalchemy.pool import StaticPool

from database import models  # noqa: F401  (registers models on Base.metadata)
from database.base import Base, create_engine_and_sessionmaker


@pytest_asyncio.fixture
async def session_factory():
    """Provide a session factory bound to a fresh in-memory database.

    ``StaticPool`` keeps a single underlying connection so the schema created here
    is visible to sessions handed out from the factory.
    """
    engine, factory = create_engine_and_sessionmaker(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield factory
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def session(session_factory):
    """Provide a single AsyncSession for a test."""
    async with session_factory() as s:
        yield s
