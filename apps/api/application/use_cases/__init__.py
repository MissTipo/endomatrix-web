"""
application.use_cases

All application use cases, importable from one place.

    from application.use_cases import LogDailyEntry, GeneratePattern
"""

from .cycle_baseline import (
    SetCycleBaseline,
    SetCycleBaselineCommand,
    SetCycleBaselineResult,
    UpdateCycleBaseline,
    UpdateCycleBaselineCommand,
    UpdateCycleBaselineResult,
)
from .home import (
    GenerateEarlyFeedback,
    GenerateEarlyFeedbackCommand,
    GenerateEarlyFeedbackResult,
    GetHomeState,
    GetHomeStateCommand,
    HomeState,
)
from .log_daily_entry import (
    LogDailyEntry,
    LogDailyEntryCommand,
    LogDailyEntryResult,
    INSIGHT_UNLOCK_THRESHOLD,
)
from .pattern import (
    GeneratePattern,
    GeneratePatternCommand,
    GeneratePatternResult,
    GetPatternSummary,
    GetPatternSummaryCommand,
    GetPatternSummaryResult,
)

__all__ = [
    # Cycle baseline
    "SetCycleBaseline",
    "SetCycleBaselineCommand",
    "SetCycleBaselineResult",
    "UpdateCycleBaseline",
    "UpdateCycleBaselineCommand",
    "UpdateCycleBaselineResult",
    # Home
    "GenerateEarlyFeedback",
    "GenerateEarlyFeedbackCommand",
    "GenerateEarlyFeedbackResult",
    "GetHomeState",
    "GetHomeStateCommand",
    "HomeState",
    # Log
    "LogDailyEntry",
    "LogDailyEntryCommand",
    "LogDailyEntryResult",
    "INSIGHT_UNLOCK_THRESHOLD",
    # Pattern
    "GeneratePattern",
    "GeneratePatternCommand",
    "GeneratePatternResult",
    "GetPatternSummary",
    "GetPatternSummaryCommand",
    "GetPatternSummaryResult",
]
