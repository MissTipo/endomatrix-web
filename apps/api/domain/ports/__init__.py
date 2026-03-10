"""
domain.ports

Public API for the EndoMatrix domain ports layer.

These are the abstract interfaces that define what the domain
needs from the outside world. The infrastructure layer provides
concrete implementations. Tests provide in-memory fakes.

Import from here:
    from domain.ports import ILogRepository, ICycleRepository
"""

from .cycle_repository import ICycleRepository
from .event_publisher import IEventPublisher
from .log_repository import ILogRepository
from .pattern_repository import IPatternRepository

__all__ = [
    "ICycleRepository",
    "IEventPublisher",
    "ILogRepository",
    "IPatternRepository",
]
