"""
presentation.routers.logs

POST /logs — submit a daily log entry

If the log crosses the 30-day insight threshold, pattern generation
is triggered inline before returning. This is acceptable at MVP scale:
pattern generation is a fast, synchronous operation over a small dataset.
When the dataset grows or latency becomes a concern, move this to a
background task (FastAPI BackgroundTasks or a job queue).
"""

from __future__ import annotations

import logging
from uuid import UUID

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, status

from application.use_cases import (
    GeneratePattern,
    GeneratePatternCommand,
    LogDailyEntry,
    LogDailyEntryCommand,
)
from presentation.dependencies import (
    get_current_user_id,
    get_generate_pattern_use_case,
    get_log_daily_entry_use_case,
)
from presentation.schemas.log import LogDailyEntryRequest, LogDailyEntryResponse

router = APIRouter(prefix="/logs", tags=["logs"])


@router.post(
    "",
    response_model=LogDailyEntryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit daily log",
    description=(
        "Submit today's symptom log. If a log already exists for this date, "
        "it is superseded (soft-deleted) and replaced. "
        "If this log crosses the 30-day threshold, pattern generation runs "
        "before the response is returned."
    ),
)
def submit_log(
    body: LogDailyEntryRequest,
    user_id: UUID = Depends(get_current_user_id),
    log_use_case: LogDailyEntry = Depends(get_log_daily_entry_use_case),
    pattern_use_case: GeneratePattern = Depends(get_generate_pattern_use_case),
) -> LogDailyEntryResponse:
    command = LogDailyEntryCommand(
        user_id=user_id,
        logged_date=body.logged_date,
        pain_level=body.pain_level,
        energy_level=body.energy_level,
        dominant_symptom=body.dominant_symptom,
        mood_level=body.mood_level,
        note=body.note,
    )
    result = log_use_case.execute(command)

    # Trigger pattern generation when the threshold is crossed.
    # Fire-and-forget errors here: if pattern generation fails, the log
    # was still saved. The insights screen will show "not yet unlocked"
    # until the next successful generation.
    if result.insight_threshold_crossed:
        try:
            pattern_use_case.execute(GeneratePatternCommand(user_id=user_id))
        except Exception:
            logger.exception(
                "Pattern generation failed for user %s after threshold crossed. "
                "Log was saved. Insights will unlock on next successful generation.",
                user_id,
            )

    log = result.log

    return LogDailyEntryResponse(
        log_id=log.id,
        logged_date=log.logged_date,
        cycle_day=log.cycle_day,
        cycle_phase=log.cycle_phase.display_name,
        pain_level=log.pain_level.value,
        energy_level=log.energy_level.value,
        mood_level=log.mood_level.value if log.mood_level is not None else None,
        dominant_symptom=log.dominant_symptom.value,
        log_count=result.log_count,
        was_superseded=result.was_superseded,
        insight_threshold_crossed=result.insight_threshold_crossed,
        message="Updated." if result.was_superseded else "Saved.",
    )
