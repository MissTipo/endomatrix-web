"""
tests/presentation/test_insights.py

Tests for GET /insights and POST /insights/generate.

What we are testing:
    GET /insights:
        - 200 on success
        - Locked state: is_unlocked=False, all pattern fields null
        - Unlocked state: full pattern returned with correct mapping
        - Phase display names used, not enum values
        - Prediction absent when pattern has none
        - display_confidence thresholds map correctly
    POST /insights/generate:
        - 200 on success
        - was_generated=True returns pattern_id
        - was_generated=False returns no pattern_id
        - Missing header → 401
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from unittest.mock import MagicMock

import pytest

from application.use_cases import (
    GeneratePatternResult,
    GetPatternSummaryResult,
)
from domain.models.cycle import CyclePhase
from domain.models.pattern import (
    CyclePrediction,
    EscalationSpeed,
    PhasePattern,
    PatternResult,
    SeverityTrend,
    SymptomCluster,
)
from domain.models.symptom import Symptom
from presentation.dependencies import (
    get_generate_pattern_use_case,
    get_pattern_summary_use_case,
)
from presentation.app import app
from tests.presentation.conftest import AUTH_HEADERS, USER_ID, mock_use_case


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PATTERN_ID = uuid.uuid4()


def _make_pattern(*, include_prediction: bool = True) -> PatternResult:
    cluster = SymptomCluster(
        symptoms=frozenset({Symptom.PELVIC_PAIN, Symptom.BLOATING}),
        typical_phase=CyclePhase.LUTEAL,
        occurrence_rate=0.8,
    )
    phase_pat = PhasePattern(
        phase=CyclePhase.LUTEAL,
        onset_day_range=(20, 24),
        average_pain=6.5,
        average_energy=3.2,
        dominant_symptoms=[Symptom.PELVIC_PAIN],
        severity_trend=SeverityTrend.ESCALATING,
        log_count=20,
    )
    prediction = (
        CyclePrediction(
            high_symptom_day_range=(20, 26),
            predicted_dominant_phase=CyclePhase.LUTEAL,
            confidence=0.75,
            basis_cycles=2,
        )
        if include_prediction
        else None
    )
    return PatternResult(
        id=PATTERN_ID,
        user_id=USER_ID,
        generated_at=datetime(2026, 3, 1, 8, 0, 0),
        cycles_analyzed=2,
        total_logs=35,
        symptom_onset_range=(20, 22),
        escalation_speed=EscalationSpeed.SHARP,
        symptom_clusters=[cluster],
        phase_patterns=[phase_pat],
        severity_trend=SeverityTrend.ESCALATING,
        prediction=prediction,
    )


def _locked_summary() -> GetPatternSummaryResult:
    return GetPatternSummaryResult(
        pattern=None,
        log_count=10,
        logs_until_unlock=20,
        is_unlocked=False,
    )


def _unlocked_summary(*, include_prediction: bool = True) -> GetPatternSummaryResult:
    return GetPatternSummaryResult(
        pattern=_make_pattern(include_prediction=include_prediction),
        log_count=35,
        logs_until_unlock=0,
        is_unlocked=True,
    )


# ---------------------------------------------------------------------------
# GET /insights — locked state
# ---------------------------------------------------------------------------

class TestGetInsightsLocked:

    def test_returns_200(self, client):
        uc = mock_use_case(return_value=_locked_summary())
        app.dependency_overrides[get_pattern_summary_use_case] = lambda: uc

        resp = client.get("/insights", headers=AUTH_HEADERS)

        assert resp.status_code == 200

    def test_is_unlocked_false(self, client):
        uc = mock_use_case(return_value=_locked_summary())
        app.dependency_overrides[get_pattern_summary_use_case] = lambda: uc

        body = client.get("/insights", headers=AUTH_HEADERS).json()

        assert body["is_unlocked"] is False

    def test_pattern_fields_are_null(self, client):
        uc = mock_use_case(return_value=_locked_summary())
        app.dependency_overrides[get_pattern_summary_use_case] = lambda: uc

        body = client.get("/insights", headers=AUTH_HEADERS).json()

        assert body["pattern_id"] is None
        assert body["cycles_analyzed"] is None
        assert body["symptom_clusters"] is None
        assert body["phase_patterns"] is None
        assert body["prediction"] is None

    def test_progress_fields_populated(self, client):
        uc = mock_use_case(return_value=_locked_summary())
        app.dependency_overrides[get_pattern_summary_use_case] = lambda: uc

        body = client.get("/insights", headers=AUTH_HEADERS).json()

        assert body["log_count"] == 10
        assert body["logs_until_unlock"] == 20


# ---------------------------------------------------------------------------
# GET /insights — unlocked state
# ---------------------------------------------------------------------------

class TestGetInsightsUnlocked:

    def test_is_unlocked_true(self, client):
        uc = mock_use_case(return_value=_unlocked_summary())
        app.dependency_overrides[get_pattern_summary_use_case] = lambda: uc

        body = client.get("/insights", headers=AUTH_HEADERS).json()

        assert body["is_unlocked"] is True

    def test_pattern_id_present(self, client):
        uc = mock_use_case(return_value=_unlocked_summary())
        app.dependency_overrides[get_pattern_summary_use_case] = lambda: uc

        body = client.get("/insights", headers=AUTH_HEADERS).json()

        assert body["pattern_id"] == str(PATTERN_ID)

    def test_symptom_clusters_mapped(self, client):
        uc = mock_use_case(return_value=_unlocked_summary())
        app.dependency_overrides[get_pattern_summary_use_case] = lambda: uc

        body = client.get("/insights", headers=AUTH_HEADERS).json()
        clusters = body["symptom_clusters"]

        assert len(clusters) == 1
        assert set(clusters[0]["symptoms"]) == {Symptom.PELVIC_PAIN.value, Symptom.BLOATING.value}
        assert clusters[0]["typical_phase"] == CyclePhase.LUTEAL.display_name
        assert clusters[0]["occurrence_rate"] == 0.8

    def test_phase_patterns_mapped(self, client):
        uc = mock_use_case(return_value=_unlocked_summary())
        app.dependency_overrides[get_pattern_summary_use_case] = lambda: uc

        body = client.get("/insights", headers=AUTH_HEADERS).json()
        pp = body["phase_patterns"][0]

        assert pp["phase"] == CyclePhase.LUTEAL.display_name
        assert pp["onset_day_range"] == [20, 24]
        assert pp["average_pain"] == 6.5
        assert pp["severity_trend"] == SeverityTrend.ESCALATING.value
        assert Symptom.PELVIC_PAIN.value in pp["dominant_symptoms"]

    def test_prediction_mapped(self, client):
        uc = mock_use_case(return_value=_unlocked_summary(include_prediction=True))
        app.dependency_overrides[get_pattern_summary_use_case] = lambda: uc

        body = client.get("/insights", headers=AUTH_HEADERS).json()
        pred = body["prediction"]

        assert pred is not None
        assert pred["high_symptom_day_range"] == [20, 26]
        assert pred["predicted_dominant_phase"] == CyclePhase.LUTEAL.display_name
        assert pred["confidence"] == 0.75
        assert pred["basis_cycles"] == 2

    def test_prediction_absent_when_none(self, client):
        uc = mock_use_case(return_value=_unlocked_summary(include_prediction=False))
        app.dependency_overrides[get_pattern_summary_use_case] = lambda: uc

        body = client.get("/insights", headers=AUTH_HEADERS).json()

        assert body["prediction"] is None

    def test_display_confidence_consistent_pattern(self, client):
        uc = mock_use_case(return_value=_unlocked_summary(include_prediction=True))
        app.dependency_overrides[get_pattern_summary_use_case] = lambda: uc

        body = client.get("/insights", headers=AUTH_HEADERS).json()

        # confidence=0.75 → "consistent pattern"
        assert body["prediction"]["display_confidence"] == "consistent pattern"

    def test_display_confidence_emerging_pattern(self, client):
        pattern = _make_pattern(include_prediction=False)
        pred = CyclePrediction(
            high_symptom_day_range=(20, 26),
            predicted_dominant_phase=CyclePhase.LUTEAL,
            confidence=0.55,
            basis_cycles=2,
        )
        import dataclasses
        pattern_with_pred = dataclasses.replace(pattern, prediction=pred)
        result = GetPatternSummaryResult(
            pattern=pattern_with_pred,
            log_count=35,
            logs_until_unlock=0,
            is_unlocked=True,
        )
        uc = mock_use_case(return_value=result)
        app.dependency_overrides[get_pattern_summary_use_case] = lambda: uc

        body = client.get("/insights", headers=AUTH_HEADERS).json()

        assert body["prediction"]["display_confidence"] == "emerging pattern"

    def test_display_confidence_variable_pattern(self, client):
        pattern = _make_pattern(include_prediction=False)
        pred = CyclePrediction(
            high_symptom_day_range=(20, 26),
            predicted_dominant_phase=CyclePhase.LUTEAL,
            confidence=0.3,
            basis_cycles=2,
        )
        import dataclasses
        pattern_with_pred = dataclasses.replace(pattern, prediction=pred)
        result = GetPatternSummaryResult(
            pattern=pattern_with_pred,
            log_count=35,
            logs_until_unlock=0,
            is_unlocked=True,
        )
        uc = mock_use_case(return_value=result)
        app.dependency_overrides[get_pattern_summary_use_case] = lambda: uc

        body = client.get("/insights", headers=AUTH_HEADERS).json()

        assert body["prediction"]["display_confidence"] == "variable pattern"

    def test_phase_display_name_used_not_enum_value(self, client):
        """Phase names should be human-readable, not the raw enum string."""
        uc = mock_use_case(return_value=_unlocked_summary())
        app.dependency_overrides[get_pattern_summary_use_case] = lambda: uc

        body = client.get("/insights", headers=AUTH_HEADERS).json()

        # display_name should be something like "Luteal" not "luteal"
        assert body["phase_patterns"][0]["phase"] == CyclePhase.LUTEAL.display_name


# ---------------------------------------------------------------------------
# POST /insights/generate
# ---------------------------------------------------------------------------

class TestGenerateInsights:

    def test_returns_200(self, client):
        uc = mock_use_case(
            return_value=GeneratePatternResult(
                pattern=_make_pattern(),
                was_generated=True,
                is_first_pattern=True,
            )
        )
        app.dependency_overrides[get_generate_pattern_use_case] = lambda: uc

        resp = client.post("/insights/generate", headers=AUTH_HEADERS)

        assert resp.status_code == 200

    def test_was_generated_true_returns_pattern_id(self, client):
        uc = mock_use_case(
            return_value=GeneratePatternResult(
                pattern=_make_pattern(),
                was_generated=True,
                is_first_pattern=True,
            )
        )
        app.dependency_overrides[get_generate_pattern_use_case] = lambda: uc

        body = client.post("/insights/generate", headers=AUTH_HEADERS).json()

        assert body["was_generated"] is True
        assert body["is_first_pattern"] is True
        assert body["pattern_id"] == str(PATTERN_ID)

    def test_was_generated_false_returns_no_pattern_id(self, client):
        uc = mock_use_case(
            return_value=GeneratePatternResult(
                pattern=None,
                was_generated=False,
                is_first_pattern=False,
            )
        )
        app.dependency_overrides[get_generate_pattern_use_case] = lambda: uc

        body = client.post("/insights/generate", headers=AUTH_HEADERS).json()

        assert body["was_generated"] is False
        assert body["pattern_id"] is None

    def test_missing_header_returns_401_or_422(self, client):
        resp = client.post("/insights/generate")

        assert resp.status_code in (401, 422)
