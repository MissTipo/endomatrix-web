"""
Domain Events

Immutable records of things that happened in the domain.

These serve two purposes:
1. They are the source of truth for the audit log. Every event that
   touches health data is recorded. The infrastructure layer persists
   them to the audit_events table.
2. They can drive side effects without coupling the domain to them.
   For example, PatternGenerated can trigger a notification without
   the pattern engine knowing notifications exist.

Design rules:
- Events are frozen dataclasses. They record history; history does not change.
- Every event carries occurred_at (when it happened) and user_id (whose data).
- Event names are past tense: LogCreated, not CreateLog.
- No business logic lives here. Events are records, not actors.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from .cycle import CyclePhase
from .symptom import Symptom


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DomainEvent:
    """Base class for all domain events."""
    user_id: UUID
    occurred_at: datetime


# ---------------------------------------------------------------------------
# Log events
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LogCreated(DomainEvent):
    """
    Raised when a user successfully submits a daily log.

    log_id:         The ID of the newly created DailyLog.
    logged_date:    The calendar date the log represents.
    cycle_phase:    The inferred phase at the time of logging.
    pain_level:     The recorded pain score (0–10).
    energy_level:   The recorded energy score (0–10).
    """

    log_id: UUID
    logged_date: str          # ISO date string: "2025-03-07"
    cycle_phase: CyclePhase
    pain_level: int
    energy_level: int


@dataclass(frozen=True)
class LogSuperseded(DomainEvent):
    """
    Raised when a user corrects a previously submitted log.

    The original log is never deleted or mutated — it is marked
    superseded and a new log is created. Both records persist.

    original_log_id:  The log that was replaced.
    new_log_id:       The corrected log.
    logged_date:      The date both logs refer to.
    """

    original_log_id: UUID
    new_log_id: UUID
    logged_date: str


# ---------------------------------------------------------------------------
# Cycle baseline events
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CycleBaselineSet(DomainEvent):
    """
    Raised when a user sets their cycle baseline for the first time
    (during onboarding).

    last_period_start:    ISO date string of the reported period start.
    average_cycle_length: The reported cycle length, or None if irregular.
    is_irregular:         Whether the user reported an irregular cycle.
    """

    last_period_start: str
    average_cycle_length: int | None
    is_irregular: bool


@dataclass(frozen=True)
class CycleBaselineUpdated(DomainEvent):
    """
    Raised when a user updates their cycle info from Settings.

    Records the previous and new values for full audit trail.
    """

    previous_last_period_start: str
    new_last_period_start: str
    previous_cycle_length: int | None
    new_cycle_length: int | None


# ---------------------------------------------------------------------------
# Pattern events
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PatternGenerated(DomainEvent):
    """
    Raised when the pattern engine produces a new PatternResult.

    pattern_id:      The ID of the PatternResult.
    cycles_analyzed: Number of cycles the analysis covered.
    total_logs:      Number of daily logs that fed the analysis.
    is_first:        True if this is the user's first pattern result
                     (the 30-day unlock moment).
    """

    pattern_id: UUID
    cycles_analyzed: int
    total_logs: int
    is_first: bool


@dataclass(frozen=True)
class EarlyFeedbackGenerated(DomainEvent):
    """
    Raised when an early reinforcement message is produced for the
    Home screen (day 7–30 period).

    trigger_phase: The cycle phase that prompted this message, if any.
    log_count:     How many logs the message is based on.
    """

    trigger_phase: CyclePhase | None
    log_count: int


# ---------------------------------------------------------------------------
# Account / consent events
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ConsentRecorded(DomainEvent):
    """
    Raised when a user gives explicit consent during onboarding.

    consent_version: The version string of the consent document agreed to.
                     Must be tracked so changes to consent terms are auditable.
    """

    consent_version: str


@dataclass(frozen=True)
class DataDeletionRequested(DomainEvent):
    """
    Raised when a user requests deletion of all their data from Settings.

    This event triggers the deletion workflow in the application layer.
    The event itself is retained in the audit log even after deletion
    completes — it is the record that a deletion occurred.

    requested_at is inherited from occurred_at on the base class.
    """
    pass
