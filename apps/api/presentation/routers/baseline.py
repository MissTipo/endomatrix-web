"""
presentation.routers.baseline

POST /baseline   — set cycle baseline (onboarding)
PUT  /baseline   — update cycle baseline (user corrects their data)

Both require a valid X-User-Id header.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status

from application.use_cases import (
    SetCycleBaseline,
    SetCycleBaselineCommand,
    UpdateCycleBaseline,
    UpdateCycleBaselineCommand,
)
from presentation.dependencies import (
    get_current_user_id,
    get_set_cycle_baseline_use_case,
    get_update_cycle_baseline_use_case,
)
from presentation.schemas.cycle import (
    CycleBaselineResponse,
    SetCycleBaselineRequest,
    UpdateCycleBaselineRequest,
)

router = APIRouter(prefix="/baseline", tags=["baseline"])


@router.post(
    "",
    response_model=CycleBaselineResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Set cycle baseline",
    description=(
        "Record the user's cycle information during onboarding. "
        "Must be called before any daily log can be submitted."
    ),
)
def set_baseline(
    body: SetCycleBaselineRequest,
    user_id: UUID = Depends(get_current_user_id),
    use_case: SetCycleBaseline = Depends(get_set_cycle_baseline_use_case),
) -> CycleBaselineResponse:
    command = SetCycleBaselineCommand(
        user_id=user_id,
        last_period_start=body.last_period_start,
        average_cycle_length=body.average_cycle_length,
        is_irregular=body.is_irregular,
    )
    result = use_case.execute(command)
    baseline = result.baseline

    return CycleBaselineResponse(
        user_id=baseline.user_id,
        last_period_start=baseline.last_period_start,
        average_cycle_length=baseline.average_cycle_length,
        is_irregular=baseline.is_irregular,
        updated_at=baseline.updated_at,
        has_reliable_baseline=baseline.has_reliable_baseline,
    )


@router.put(
    "",
    response_model=CycleBaselineResponse,
    status_code=status.HTTP_200_OK,
    summary="Update cycle baseline",
    description="Correct or update the user's cycle information.",
)
def update_baseline(
    body: UpdateCycleBaselineRequest,
    user_id: UUID = Depends(get_current_user_id),
    use_case: UpdateCycleBaseline = Depends(get_update_cycle_baseline_use_case),
) -> CycleBaselineResponse:
    command = UpdateCycleBaselineCommand(
        user_id=user_id,
        last_period_start=body.last_period_start,
        average_cycle_length=body.average_cycle_length,
        is_irregular=body.is_irregular,
    )
    result = use_case.execute(command)
    baseline = result.baseline

    return CycleBaselineResponse(
        user_id=baseline.user_id,
        last_period_start=baseline.last_period_start,
        average_cycle_length=baseline.average_cycle_length,
        is_irregular=baseline.is_irregular,
        updated_at=baseline.updated_at,
        has_reliable_baseline=baseline.has_reliable_baseline,
    )
