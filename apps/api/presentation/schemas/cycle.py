"""
presentation.schemas.cycle

Pydantic request and response models for cycle baseline endpoints.

These are the API's public contract — separate from domain models.
Domain models are internal; schemas are what callers send and receive.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------

class SetCycleBaselineRequest(BaseModel):
    last_period_start: date = Field(
        description="First day of the most recent period. ISO date format (YYYY-MM-DD)."
    )
    average_cycle_length: Optional[int] = Field(
        default=None,
        ge=21,
        le=45,
        description="Average cycle length in days. Omit or set null if irregular.",
    )
    is_irregular: bool = Field(
        default=False,
        description="True if cycles are irregular and cycle length is unknown.",
    )

    @field_validator("last_period_start")
    @classmethod
    def last_period_start_not_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("last_period_start cannot be in the future.")
        return v


class UpdateCycleBaselineRequest(BaseModel):
    last_period_start: date = Field(
        description="Updated first day of the most recent period."
    )
    average_cycle_length: Optional[int] = Field(
        default=None,
        ge=21,
        le=45,
    )
    is_irregular: bool = Field(default=False)

    @field_validator("last_period_start")
    @classmethod
    def last_period_start_not_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("last_period_start cannot be in the future.")
        return v


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------

class CycleBaselineResponse(BaseModel):
    user_id: UUID
    last_period_start: date
    average_cycle_length: Optional[int]
    is_irregular: bool
    updated_at: datetime
    has_reliable_baseline: bool

    model_config = {"from_attributes": True}
