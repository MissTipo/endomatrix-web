"""
presentation.schemas.pattern

Pydantic response models for the Home screen and Insights screen.

These flatten nested domain objects into clean JSON shapes.
The frontend never receives raw domain models — only these schemas.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Home screen
# ---------------------------------------------------------------------------

class HomeStateResponse(BaseModel):
    has_logged_today: bool
    log_count: int
    current_cycle_day: Optional[int]
    current_phase: Optional[str]
    phase_is_reliable: bool
    streak: int
    logs_until_unlock: int
    is_insights_unlocked: bool
    early_feedback: Optional[str]


# ---------------------------------------------------------------------------
# Insights screen
# ---------------------------------------------------------------------------

class SymptomClusterResponse(BaseModel):
    symptoms: list[str]
    typical_phase: str
    occurrence_rate: float


class PhasePatternResponse(BaseModel):
    phase: str
    onset_day_range: tuple[int, int]
    average_pain: float
    average_energy: float
    dominant_symptoms: list[str]
    severity_trend: str
    log_count: int
    has_sufficient_data: bool


class CyclePredictionResponse(BaseModel):
    high_symptom_day_range: tuple[int, int]
    predicted_dominant_phase: str
    confidence: float
    basis_cycles: int
    display_confidence: str  # "consistent pattern" / "emerging pattern" / "variable pattern"


class PatternSummaryResponse(BaseModel):
    is_unlocked: bool
    log_count: int
    logs_until_unlock: int
    # All fields below are None when is_unlocked is False
    pattern_id: Optional[UUID] = None
    cycles_analyzed: Optional[int] = None
    total_logs: Optional[int] = None
    symptom_onset_range: Optional[tuple[int, int]] = None
    escalation_speed: Optional[str] = None
    severity_trend: Optional[str] = None
    symptom_clusters: Optional[list[SymptomClusterResponse]] = None
    phase_patterns: Optional[list[PhasePatternResponse]] = None
    prediction: Optional[CyclePredictionResponse] = None


class GeneratePatternResponse(BaseModel):
    was_generated: bool
    is_first_pattern: bool
    pattern_id: Optional[UUID] = None
