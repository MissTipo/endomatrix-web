"""
domain.models

Public API for the EndoMatrix domain model layer.

Import from here, not from the individual modules:

    from domain.models import DailyLog, Score, CyclePhase, PatternResult

This gives us the freedom to reorganise the internal module structure
without breaking imports elsewhere in the codebase.
"""

from .cycle import CycleBaseline, CyclePhase, Score
from .daily_log import DailyLog, NOTE_MAX_LENGTH
from .events import (
    ConsentRecorded,
    CycleBaselineSet,
    CycleBaselineUpdated,
    DataDeletionRequested,
    DomainEvent,
    EarlyFeedbackGenerated,
    LogCreated,
    LogSuperseded,
    PatternGenerated,
)
from .pattern import (
    CyclePrediction,
    EarlyFeedback,
    EscalationSpeed,
    PatternResult,
    PhasePattern,
    SeverityTrend,
    SymptomCluster,
)
from .symptom import Symptom

__all__ = [
    # Cycle
    "CycleBaseline",
    "CyclePhase",
    "Score",
    # Daily log
    "DailyLog",
    "NOTE_MAX_LENGTH",
    # Pattern
    "CyclePrediction",
    "EarlyFeedback",
    "EscalationSpeed",
    "PatternResult",
    "PhasePattern",
    "SeverityTrend",
    "SymptomCluster",
    # Symptom
    "Symptom",
    # Events
    "ConsentRecorded",
    "CycleBaselineSet",
    "CycleBaselineUpdated",
    "DataDeletionRequested",
    "DomainEvent",
    "EarlyFeedbackGenerated",
    "LogCreated",
    "LogSuperseded",
    "PatternGenerated",
]
