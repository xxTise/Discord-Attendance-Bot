"""ORM models and enums for the check-in domain."""

from __future__ import annotations

import enum
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy import (
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EventType(enum.Enum):
    """Type of a daily event."""

    PRACTICE = "practice"
    MATCH = "match"
    TOURNAMENT = "tournament"
    LEAGUE_MATCH = "league_match"
    FRIENDLY = "friendly"
    TRIALS = "trials"

    @property
    def label(self) -> str:
        """Human-friendly display name, e.g. ``LEAGUE_MATCH`` -> 'League Match'."""
        return self.value.replace("_", " ").title()


class EventStatus(enum.Enum):
    """Whether responses can still be changed."""

    OPEN = "open"
    LOCKED = "locked"


class ResponseState(enum.Enum):
    """A player's availability for an event."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    # LATE is deprecated: the Late response option was removed from the UI. The
    # value is retained only so historical rows already in the database still load.
    LATE = "late"


class Player(Base):
    """A Discord member tracked by the bot."""

    __tablename__ = "players"

    id: Mapped[int] = mapped_column(primary_key=True)
    discord_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    responses: Mapped[list["Response"]] = relationship(back_populates="player")


class Event(Base):
    """A single daily check-in. One event per calendar day."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_date: Mapped[date] = mapped_column(Date, unique=True, index=True)
    event_type: Mapped[EventType] = mapped_column(
        SAEnum(EventType), default=EventType.PRACTICE
    )
    # Kickoff time as local "HH:MM" (24-hour) in the configured timezone.
    start_time: Mapped[str] = mapped_column(String(5), default="19:00")
    # Comma-separated minute-offsets whose pre-kickoff ping has already fired.
    pinged_offsets: Mapped[str] = mapped_column(String(50), default="")
    status: Mapped[EventStatus] = mapped_column(
        SAEnum(EventStatus), default=EventStatus.OPEN
    )
    message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    channel_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    lock_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    locked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    locked_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    responses: Mapped[list["Response"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )


class Response(Base):
    """A player's response to a specific event (one per player per event)."""

    __tablename__ = "responses"
    __table_args__ = (
        UniqueConstraint("event_id", "player_id", name="uq_response_event_player"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    state: Mapped[ResponseState] = mapped_column(SAEnum(ResponseState))
    eta: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    event: Mapped["Event"] = relationship(back_populates="responses")
    player: Mapped["Player"] = relationship(back_populates="responses")
