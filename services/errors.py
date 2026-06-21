"""Domain exceptions raised by the service layer.

Cogs translate these into user-facing Discord messages.
"""

from __future__ import annotations


class ServiceError(Exception):
    """Base class for all service-layer errors."""


class EventLockedError(ServiceError):
    """Raised when a write is attempted on a locked event."""


class ResponseValidationError(ServiceError):
    """Raised when a response is missing required data (e.g. a Late ETA)."""


class EventStateError(ServiceError):
    """Raised when an operation is invalid for the event's current state."""
