"""
presentation.routers.home

GET /home — everything the Home screen needs in one call

Read-only. No writes happen here. The frontend polls this on every
app open and after a successful log submission.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from datetime import date

from application.use_cases import GetHomeState, GetHomeStateCommand
from presentation.dependencies import get_current_user_id, get_home_state_use_case
from presentation.schemas.pattern import HomeStateResponse

router = APIRouter(prefix="/home", tags=["home"])


@router.get(
    "",
    response_model=HomeStateResponse,
    summary="Get home screen state",
    description=(
        "Returns everything the Home screen needs: today's log status, "
        "current cycle phase, streak, progress toward insight unlock, "
        "and the latest early feedback message."
    ),
)
def get_home(
    user_id: UUID = Depends(get_current_user_id),
    use_case: GetHomeState = Depends(get_home_state_use_case),
) -> HomeStateResponse:
    command = GetHomeStateCommand(user_id=user_id, today=date.today())
    state = use_case.execute(command)

    return HomeStateResponse(
        has_logged_today=state.has_logged_today,
        log_count=state.log_count,
        current_cycle_day=state.current_cycle_day,
        current_phase=state.current_phase,
        phase_is_reliable=state.phase_is_reliable,
        streak=state.streak,
        logs_until_unlock=state.logs_until_unlock,
        is_insights_unlocked=state.is_insights_unlocked,
        early_feedback=state.early_feedback,
    )
