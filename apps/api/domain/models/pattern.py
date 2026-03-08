"""
Pattern

The output types produced by the pattern engine.

These models represent what EndoMatrix tells the user — the insight page,
the early feedback cards, and eventually the cycle prediction. They are
the product's core value expressed as data structures.

Nothing in this file touches a database or an HTTP request. The engine
produces these; the presentation layer renders them.

Models defined here:
    SeverityTrend       — is it getting worse, better, or staying the same?
    EscalationSpeed     — how quickly do symptoms intensify from onset?
    SymptomCluster      — symptoms that appear together
    PhasePattern        — what a specific cycle phase looks like for this user
    CyclePrediction     — soft prediction for the next cycle (MVP)
    PatternResult       — the complete output of a pattern analysis run
    EarlyFeedback       — the day 7–14 reinforcement card
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from .cycle import CyclePhase, Score
from .symptom import Symptom


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class SeverityTrend(str, Enum):
    """
    The direction of symptom severity over the analyzed period.

    ESCALATING: symptoms are getting worse across cycles.
    IMPROVING:  symptoms are getting better across cycles.
    STABLE:     symptoms are consistent cycle to cycle.
    VARIABLE:   symptoms fluctuate without a clear direction.

    INSUFFICIENT_DATA: fewer cycles than the minimum required for
    trend detection. Not an error — this is the honest answer when
    data is limited.
    """

    ESCALATING = "escalating"
    IMPROVING = "improving"
    STABLE = "stable"
    VARIABLE = "variable"
    INSUFFICIENT_DATA = "insufficient_data"


class EscalationSpeed(str, Enum):
    """
    How quickly symptoms intensify from their onset day.

    GRADUAL:  symptoms build slowly over several days.
    MODERATE: symptoms build over 2–3 days.
    SHARP:    symptoms peak within 1 day of onset.
    UNKNOWN:  not enough data to classify.
    """

    GRADUAL = "gradual"
    MODERATE = "moderate"
    SHARP = "sharp"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# SymptomCluster
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SymptomCluster:
    """
    A set of symptoms that tend to appear together for this user.

    occurrence_rate is the fraction of symptomatic days where this
    exact cluster was observed (0.0–1.0). A cluster with an
    occurrence_rate below 0.3 is typically not surfaced in the UI.

    typical_phase is the cycle phase where this cluster most commonly
    appears. May be CyclePhase.UNKNOWN if it is not phase-specific.

    Example:
        SymptomCluster(
            symptoms=frozenset({Symptom.MOOD_CRASH, Symptom.BRAIN_FOG}),
            typical_phase=CyclePhase.LUTEAL,
            occurrence_rate=0.72,
        )
        # "Mood crash and brain fog appear together on 72% of your
        #  symptomatic days, most often in your luteal phase."
    """

    symptoms: frozenset[Symptom]
    typical_phase: CyclePhase
    occurrence_rate: float

    def __post_init__(self) -> None:
        if not (0.0 <= self.occurrence_rate <= 1.0):
            raise ValueError(
                f"occurrence_rate must be between 0.0 and 1.0, got {self.occurrence_rate}"
            )
        if len(self.symptoms) < 2:
            raise ValueError(
                "A SymptomCluster must contain at least 2 symptoms. "
                "Single symptoms are not clusters."
            )

    @property
    def is_notable(self) -> bool:
        """True if this cluster appears frequently enough to surface in the UI."""
        return self.occurrence_rate >= 0.3

    def contains(self, symptom: Symptom) -> bool:
        return symptom in self.symptoms


# ---------------------------------------------------------------------------
# PhasePattern
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PhasePattern:
    """
    What a specific cycle phase looks like for this user, derived from
    multiple cycles of logged data.

    onset_day_range:      The typical cycle day range when symptoms begin
                          in this phase. Expressed as (earliest, latest).
    average_pain:         Mean pain score across all logs in this phase.
    average_energy:       Mean energy score across all logs in this phase.
    dominant_symptoms:    The most frequently logged symptoms in this phase,
                          ordered by frequency descending. Maximum 3.
    severity_trend:       Whether this phase is getting worse, better, or
                          holding steady across the analyzed cycles.
    log_count:            Number of daily logs that contributed to this pattern.
                          Exposed so the UI can qualify how confident the
                          pattern is — "based on 12 days of data" vs 3.

    A PhasePattern with log_count < 7 should be presented with a
    qualification in the UI. The engine does not suppress it — that is
    a presentation layer decision.
    """

    phase: CyclePhase
    onset_day_range: tuple[int, int]
    average_pain: float
    average_energy: float
    dominant_symptoms: list[Symptom]
    severity_trend: SeverityTrend
    log_count: int

    def __post_init__(self) -> None:
        start, end = self.onset_day_range
        if start > end:
            raise ValueError(
                f"onset_day_range start ({start}) must be <= end ({end})"
            )
        if start < 1:
            raise ValueError(
                f"onset_day_range start must be >= 1, got {start}"
            )
        if not (0.0 <= self.average_pain <= 10.0):
            raise ValueError(f"average_pain must be 0–10, got {self.average_pain}")
        if not (0.0 <= self.average_energy <= 10.0):
            raise ValueError(f"average_energy must be 0–10, got {self.average_energy}")
        if len(self.dominant_symptoms) > 3:
            raise ValueError(
                f"dominant_symptoms may contain at most 3 entries, "
                f"got {len(self.dominant_symptoms)}"
            )
        if self.log_count < 0:
            raise ValueError(f"log_count cannot be negative, got {self.log_count}")

    @property
    def is_high_burden(self) -> bool:
        """True if this phase shows above-average symptom burden."""
        return self.average_pain >= 6.0 or self.average_energy <= 4.0

    @property
    def has_sufficient_data(self) -> bool:
        """
        True if enough logs exist to present this pattern with confidence.
        Threshold of 7 represents roughly one full phase across one cycle.
        """
        return self.log_count >= 7


# ---------------------------------------------------------------------------
# CyclePrediction
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CyclePrediction:
    """
    A soft prediction for the next cycle, generated after sufficient data.

    This is not a clinical forecast. It is pattern extrapolation.
    The UI must present this with qualifying language.

    high_symptom_day_range: The cycle day range most likely to carry
                             the highest symptom burden next cycle.
    predicted_dominant_phase: The phase expected to be most symptomatic.
    confidence:              A 0.0–1.0 score representing how consistent
                             the past data is. Low confidence = high
                             variability in past cycles.
    basis_cycles:            Number of cycles this prediction is based on.
                             Exposed so the UI can say "based on 3 cycles."

    CyclePrediction is only generated when basis_cycles >= 2.
    The engine will not produce one from a single cycle.
    """

    high_symptom_day_range: tuple[int, int]
    predicted_dominant_phase: CyclePhase
    confidence: float
    basis_cycles: int

    MIN_BASIS_CYCLES: int = 2

    def __post_init__(self) -> None:
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                f"confidence must be 0.0–1.0, got {self.confidence}"
            )
        if self.basis_cycles < self.MIN_BASIS_CYCLES:
            raise ValueError(
                f"CyclePrediction requires at least {self.MIN_BASIS_CYCLES} cycles, "
                f"got {self.basis_cycles}"
            )
        start, end = self.high_symptom_day_range
        if start > end:
            raise ValueError(
                f"high_symptom_day_range start ({start}) must be <= end ({end})"
            )

    @property
    def is_high_confidence(self) -> bool:
        return self.confidence >= 0.7

    @property
    def display_confidence(self) -> str:
        """Human-readable confidence label for the UI."""
        if self.confidence >= 0.7:
            return "consistent pattern"
        if self.confidence >= 0.4:
            return "emerging pattern"
        return "variable pattern"


# ---------------------------------------------------------------------------
# PatternResult
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PatternResult:
    """
    The complete output of a single pattern analysis run for one user.

    This is what the Insights screen renders.

    Fields:
        id:                  Unique ID for this analysis run.
        user_id:             The user this analysis belongs to.
        generated_at:        When this result was produced.
        cycles_analyzed:     Number of complete or partial cycles in the
                             input data window.
        total_logs:          Total daily logs analyzed.
        symptom_onset_range: The typical cycle day range when symptoms
                             first appear across the analyzed period.
        escalation_speed:    How quickly symptoms intensify from onset.
        symptom_clusters:    Co-occurring symptom groups detected.
        phase_patterns:      Per-phase breakdowns.
        severity_trend:      Overall trend across the analyzed period.
        prediction:          Next cycle prediction. None if insufficient
                             data (fewer than 2 cycles).

    A PatternResult is generated after 30 days of logs (v0) or after
    2+ full cycles (MVP). It is stored and versioned — each run
    produces a new record, it does not overwrite the previous one.
    """

    id: UUID
    user_id: UUID
    generated_at: datetime
    cycles_analyzed: int
    total_logs: int
    symptom_onset_range: tuple[int, int]
    escalation_speed: EscalationSpeed
    symptom_clusters: list[SymptomCluster]
    phase_patterns: list[PhasePattern]
    severity_trend: SeverityTrend
    prediction: Optional[CyclePrediction] = None

    def __post_init__(self) -> None:
        if self.cycles_analyzed < 0:
            raise ValueError(f"cycles_analyzed cannot be negative, got {self.cycles_analyzed}")
        if self.total_logs < 0:
            raise ValueError(f"total_logs cannot be negative, got {self.total_logs}")

        start, end = self.symptom_onset_range
        if start > end:
            raise ValueError(
                f"symptom_onset_range start ({start}) must be <= end ({end})"
            )

    @property
    def has_prediction(self) -> bool:
        return self.prediction is not None

    @property
    def most_burdensome_phase(self) -> Optional[PhasePattern]:
        """
        Returns the phase pattern with the highest average pain,
        or None if no phase patterns exist.
        """
        if not self.phase_patterns:
            return None
        return max(self.phase_patterns, key=lambda p: p.average_pain)

    @property
    def notable_clusters(self) -> list[SymptomCluster]:
        """Returns only clusters that meet the occurrence threshold for display."""
        return [c for c in self.symptom_clusters if c.is_notable]


# ---------------------------------------------------------------------------
# EarlyFeedback
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EarlyFeedback:
    """
    A single reinforcement message shown on the Home screen between
    day 7 and day 30 of the user's logging streak.

    This is not an insight — it is a habit retention signal.
    One sentence. Based on an observable pattern in the existing logs.
    Never fabricated when no pattern exists.

    Fields:
        user_id:       The user this message is for.
        message:       The sentence shown on the Home screen.
                       Must be written in plain, non-clinical language.
        generated_at:  When this message was produced.
        trigger_phase: The cycle phase that triggered this observation,
                       if applicable. Used internally; not shown to user.
        log_count:     How many logs this message is based on.
                       Never generate a message from fewer than 3 logs.

    Example messages:
        "You tend to log higher pain around this point in your cycle."
        "Energy drops often precede your highest-pain days."
        "You've logged consistently. That's building a clearer picture."
    """

    user_id: UUID
    message: str
    generated_at: datetime
    log_count: int
    trigger_phase: Optional[CyclePhase] = None

    MIN_LOGS_REQUIRED: int = 3

    def __post_init__(self) -> None:
        if not self.message.strip():
            raise ValueError("EarlyFeedback message cannot be empty")
        if self.log_count < self.MIN_LOGS_REQUIRED:
            raise ValueError(
                f"EarlyFeedback requires at least {self.MIN_LOGS_REQUIRED} logs, "
                f"got {self.log_count}"
            )
