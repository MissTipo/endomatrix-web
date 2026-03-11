"""
presentation.schemas.log

Pydantic request and response models for daily log endpoints.
"""

from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from domain.models.symptom import Symptom


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------

class LogDailyEntryRequest(BaseModel):
    logged_date: date = Field(
        default_factory=date.today,
        description="The calendar date this log represents. Defaults to today if omitted.",
    )
    pain_level: int = Field(ge=0, le=10, description="Pain intensity, 0–10.")
    energy_level: int = Field(ge=0, le=10, description="Energy level, 0–10. Higher = more energy.")
    dominant_symptom: Symptom = Field(
        description="The single symptom that mattered most today."
    )
    mood_level: Optional[int] = Field(
        default=None,
        ge=0,
        le=10,
        description="Mood level, 0–10. Optional.",
    )
    note: Optional[str] = Field(
        default=None,
        max_length=280,
        description="Optional free-text note. One sentence, max 280 characters.",
    )

    @field_validator("logged_date")
    @classmethod
    def logged_date_not_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("logged_date cannot be in the future.")
        return v


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------

class LogDailyEntryResponse(BaseModel):
    log_id: UUID
    logged_date: date
    cycle_day: int
    cycle_phase: str
    pain_level: int
    energy_level: int
    mood_level: Optional[int]
    dominant_symptom: str
    log_count: int
    was_superseded: bool
    insight_threshold_crossed: bool
    message: str  # "Saved." or "Updated." — shown on the log screen
