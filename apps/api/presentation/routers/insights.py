"""
presentation.routers.insights

GET  /insights          — return the latest pattern summary for the Insights screen
POST /insights/generate — manually trigger pattern generation (used by the scheduler
                          or by the frontend after the 30-day threshold is crossed
                          and the inline generation in /logs failed)

Both require a valid X-User-Id header.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from application.use_cases import (
    GeneratePattern,
    GeneratePatternCommand,
    GetPatternSummary,
    GetPatternSummaryCommand,
)
from presentation.dependencies import (
    get_current_user_id,
    get_generate_pattern_use_case,
    get_pattern_summary_use_case,
)
from presentation.schemas.pattern import (
    CyclePredictionResponse,
    GeneratePatternResponse,
    PatternSummaryResponse,
    PhasePatternResponse,
    SymptomClusterResponse,
)

router = APIRouter(prefix="/insights", tags=["insights"])


def _map_pattern_summary(result) -> PatternSummaryResponse:
    """Map GetPatternSummaryResult to the response schema."""
    if not result.is_unlocked or result.pattern is None:
        return PatternSummaryResponse(
            is_unlocked=False,
            log_count=result.log_count,
            logs_until_unlock=result.logs_until_unlock,
        )

    p = result.pattern

    symptom_clusters = [
        SymptomClusterResponse(
            symptoms=[s.value for s in c.symptoms],
            typical_phase=c.typical_phase.display_name,
            occurrence_rate=c.occurrence_rate,
        )
        for c in p.symptom_clusters
    ]

    phase_patterns = [
        PhasePatternResponse(
            phase=pp.phase.display_name,
            onset_day_range=pp.onset_day_range,
            average_pain=pp.average_pain,
            average_energy=pp.average_energy,
            dominant_symptoms=[s.value for s in pp.dominant_symptoms],
            severity_trend=pp.severity_trend.value,
            log_count=pp.log_count,
            has_sufficient_data=pp.has_sufficient_data,
        )
        for pp in p.phase_patterns
    ]

    prediction = None
    if p.prediction is not None:
        pred = p.prediction
        if pred.confidence >= 0.7:
            display_confidence = "consistent pattern"
        elif pred.confidence >= 0.4:
            display_confidence = "emerging pattern"
        else:
            display_confidence = "variable pattern"

        prediction = CyclePredictionResponse(
            high_symptom_day_range=pred.high_symptom_day_range,
            predicted_dominant_phase=pred.predicted_dominant_phase.display_name,
            confidence=pred.confidence,
            basis_cycles=pred.basis_cycles,
            display_confidence=display_confidence,
        )

    return PatternSummaryResponse(
        is_unlocked=True,
        log_count=result.log_count,
        logs_until_unlock=0,
        pattern_id=p.id,
        cycles_analyzed=p.cycles_analyzed,
        total_logs=p.total_logs,
        symptom_onset_range=p.symptom_onset_range,
        escalation_speed=p.escalation_speed.value,
        severity_trend=p.severity_trend.value,
        symptom_clusters=symptom_clusters,
        phase_patterns=phase_patterns,
        prediction=prediction,
    )


@router.get(
    "",
    response_model=PatternSummaryResponse,
    summary="Get pattern summary",
    description=(
        "Returns the latest pattern analysis for the Insights screen. "
        "If the user has fewer than 30 logs or no pattern has been generated yet, "
        "is_unlocked=False and all pattern fields are null."
    ),
)
def get_insights(
    user_id: UUID = Depends(get_current_user_id),
    use_case: GetPatternSummary = Depends(get_pattern_summary_use_case),
) -> PatternSummaryResponse:
    result = use_case.execute(GetPatternSummaryCommand(user_id=user_id))
    return _map_pattern_summary(result)


@router.post(
    "/generate",
    response_model=GeneratePatternResponse,
    summary="Trigger pattern generation",
    description=(
        "Runs the pattern engine and saves the result. "
        "Returns was_generated=False (not an error) if fewer than 14 logs exist. "
        "The frontend can call this after the 30-day threshold is crossed if the "
        "automatic generation in POST /logs did not produce a result."
    ),
)
def generate_insights(
    user_id: UUID = Depends(get_current_user_id),
    use_case: GeneratePattern = Depends(get_generate_pattern_use_case),
) -> GeneratePatternResponse:
    result = use_case.execute(GeneratePatternCommand(user_id=user_id))

    return GeneratePatternResponse(
        was_generated=result.was_generated,
        is_first_pattern=result.is_first_pattern,
        pattern_id=result.pattern.id if result.pattern is not None else None,
    )
