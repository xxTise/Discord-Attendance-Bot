"""Async SQLAlchemy engine, session factory, and declarative base."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(AsyncAttrs, DeclarativeBase):
    """Declarative base for all ORM models."""


def create_engine_and_sessionmaker(
    database_url: str, **engine_kwargs: object
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Create an async engine and a session factory bound to it."""
    engine = create_async_engine(database_url, **engine_kwargs)
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    return engine, session_factory
