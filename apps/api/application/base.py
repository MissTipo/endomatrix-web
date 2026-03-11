"""
application.base

Base classes for commands and results in the application layer.

Every use case follows the same shape:
    - A Command dataclass carrying validated input
    - A Result dataclass carrying the output
    - A use case class with an execute(command) -> Result method

Commands are immutable. They represent a user's intent at a point in time.
Results are immutable. They carry what the caller needs — nothing extra.

In general, commands and results carry primitive types and IDs. The use
case is responsible for loading domain models from ports and returning
only what the caller needs to render a screen or respond to an API request.

Some result types intentionally return richer domain outputs that the
presentation layer renders directly. PatternResult and EarlyFeedback are
canonical examples — they are returned as-is rather than re-mapped to
thin DTOs at this stage. SetCycleBaselineResult and LogDailyEntryResult
also carry domain models directly for the same reason.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Command:
    """Base class for all application commands."""
    pass


@dataclass(frozen=True)
class Result:
    """Base class for all application results."""
    pass
