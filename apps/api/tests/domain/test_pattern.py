"""
Tests for domain.models.pattern

Covers:
- SymptomCluster: construction, validation, convenience methods
- PhasePattern: construction, validation, derived properties
- CyclePrediction: construction, validation, confidence helpers
- PatternResult: construction, derived properties
- EarlyFeedback: construction, validation
- SeverityTrend and EscalationSpeed: enum stability
"""

import pytest
from datetime import datetime
from uuid import uuid4

from domain.models.cycle import CyclePhase
from domain.models.symptom import Symptom
from domain.models.pattern import (
    CyclePrediction,
    EarlyFeedback,
    EscalationSpeed,
    PatternResult,
    PhasePattern,
    SeverityTrend,
    SymptomCluster,
)


# ---------------------------------------------------------------------------
# SeverityTrend and EscalationSpeed — enum stability
# ---------------------------------------------------------------------------

class TestEnumStability:

    def test_severity_trend_values(self):
        values = {t.value for t in SeverityTrend}
        assert values == {"escalating", "improving", "stable", "variable", "insufficient_data"}

    def test_escalation_speed_values(self):
        values = {e.value for e in EscalationSpeed}
        assert values == {"gradual", "moderate", "sharp", "unknown"}


# ---------------------------------------------------------------------------
# SymptomCluster
# ---------------------------------------------------------------------------

class TestSymptomCluster:

    def test_valid_cluster(self):
        cluster = SymptomCluster(
            symptoms=frozenset({Symptom.MOOD_CRASH, Symptom.BRAIN_FOG}),
            typical_phase=CyclePhase.LUTEAL,
            occurrence_rate=0.72,
        )
        assert cluster.occurrence_rate == 0.72

    def test_single_symptom_raises(self):
        with pytest.raises(ValueError, match="at least 2 symptoms"):
            SymptomCluster(
                symptoms=frozenset({Symptom.PELVIC_PAIN}),
                typical_phase=CyclePhase.MENSTRUAL,
                occurrence_rate=0.5,
            )

    def test_empty_symptoms_raises(self):
        with pytest.raises(ValueError, match="at least 2 symptoms"):
            SymptomCluster(
                symptoms=frozenset(),
                typical_phase=CyclePhase.MENSTRUAL,
                occurrence_rate=0.5,
            )

    def test_occurrence_rate_above_one_raises(self):
        with pytest.raises(ValueError, match="0.0 and 1.0"):
            SymptomCluster(
                symptoms=frozenset({Symptom.PELVIC_PAIN, Symptom.BLOATING}),
                typical_phase=CyclePhase.MENSTRUAL,
                occurrence_rate=1.1,
            )

    def test_occurrence_rate_below_zero_raises(self):
        with pytest.raises(ValueError, match="0.0 and 1.0"):
            SymptomCluster(
                symptoms=frozenset({Symptom.PELVIC_PAIN, Symptom.BLOATING}),
                typical_phase=CyclePhase.MENSTRUAL,
                occurrence_rate=-0.1,
            )

    def test_is_notable_above_threshold(self):
        cluster = SymptomCluster(
            symptoms=frozenset({Symptom.MOOD_CRASH, Symptom.BRAIN_FOG}),
            typical_phase=CyclePhase.LUTEAL,
            occurrence_rate=0.3,
        )
        assert cluster.is_notable is True

    def test_is_notable_below_threshold(self):
        cluster = SymptomCluster(
            symptoms=frozenset({Symptom.MOOD_CRASH, Symptom.BRAIN_FOG}),
            typical_phase=CyclePhase.LUTEAL,
            occurrence_rate=0.29,
        )
        assert cluster.is_notable is False

    def test_contains(self):
        cluster = SymptomCluster(
            symptoms=frozenset({Symptom.MOOD_CRASH, Symptom.BRAIN_FOG}),
            typical_phase=CyclePhase.LUTEAL,
            occurrence_rate=0.5,
        )
        assert cluster.contains(Symptom.MOOD_CRASH) is True
        assert cluster.contains(Symptom.PELVIC_PAIN) is False

    def test_cluster_is_frozen(self):
        cluster = SymptomCluster(
            symptoms=frozenset({Symptom.MOOD_CRASH, Symptom.BRAIN_FOG}),
            typical_phase=CyclePhase.LUTEAL,
            occurrence_rate=0.5,
        )
        with pytest.raises(Exception):
            cluster.occurrence_rate = 0.9  # type: ignore


# ---------------------------------------------------------------------------
# PhasePattern
# ---------------------------------------------------------------------------

class TestPhasePattern:

    def _valid_phase_pattern(self, **overrides) -> PhasePattern:
        defaults = dict(
            phase=CyclePhase.LUTEAL,
            onset_day_range=(18, 24),
            average_pain=6.5,
            average_energy=3.2,
            dominant_symptoms=[Symptom.PELVIC_PAIN, Symptom.MOOD_CRASH],
            severity_trend=SeverityTrend.STABLE,
            log_count=14,
        )
        defaults.update(overrides)
        return PhasePattern(**defaults)

    def test_valid_construction(self):
        pp = self._valid_phase_pattern()
        assert pp.phase == CyclePhase.LUTEAL

    def test_onset_range_start_after_end_raises(self):
        with pytest.raises(ValueError, match="must be <="):
            self._valid_phase_pattern(onset_day_range=(25, 18))

    def test_onset_range_start_below_one_raises(self):
        with pytest.raises(ValueError, match=">= 1"):
            self._valid_phase_pattern(onset_day_range=(0, 5))

    def test_average_pain_above_ten_raises(self):
        with pytest.raises(ValueError, match="0–10"):
            self._valid_phase_pattern(average_pain=10.1)

    def test_average_energy_below_zero_raises(self):
        with pytest.raises(ValueError, match="0–10"):
            self._valid_phase_pattern(average_energy=-0.1)

    def test_more_than_three_dominant_symptoms_raises(self):
        with pytest.raises(ValueError, match="at most 3"):
            self._valid_phase_pattern(dominant_symptoms=[
                Symptom.PELVIC_PAIN,
                Symptom.MOOD_CRASH,
                Symptom.BRAIN_FOG,
                Symptom.BLOATING,
            ])

    def test_negative_log_count_raises(self):
        with pytest.raises(ValueError, match="cannot be negative"):
            self._valid_phase_pattern(log_count=-1)

    def test_is_high_burden_high_pain(self):
        pp = self._valid_phase_pattern(average_pain=6.0, average_energy=5.0)
        assert pp.is_high_burden is True

    def test_is_high_burden_low_energy(self):
        pp = self._valid_phase_pattern(average_pain=3.0, average_energy=4.0)
        assert pp.is_high_burden is True

    def test_not_high_burden(self):
        pp = self._valid_phase_pattern(average_pain=3.0, average_energy=7.0)
        assert pp.is_high_burden is False

    def test_has_sufficient_data_at_threshold(self):
        pp = self._valid_phase_pattern(log_count=7)
        assert pp.has_sufficient_data is True

    def test_has_sufficient_data_below_threshold(self):
        pp = self._valid_phase_pattern(log_count=6)
        assert pp.has_sufficient_data is False


# ---------------------------------------------------------------------------
# CyclePrediction
# ---------------------------------------------------------------------------

class TestCyclePrediction:

    def _valid_prediction(self, **overrides) -> CyclePrediction:
        defaults = dict(
            high_symptom_day_range=(20, 26),
            predicted_dominant_phase=CyclePhase.LUTEAL,
            confidence=0.65,
            basis_cycles=2,
        )
        defaults.update(overrides)
        return CyclePrediction(**defaults)

    def test_valid_construction(self):
        pred = self._valid_prediction()
        assert pred.basis_cycles == 2

    def test_fewer_than_minimum_cycles_raises(self):
        with pytest.raises(ValueError, match="at least"):
            self._valid_prediction(basis_cycles=1)

    def test_confidence_above_one_raises(self):
        with pytest.raises(ValueError, match="0.0–1.0"):
            self._valid_prediction(confidence=1.01)

    def test_confidence_below_zero_raises(self):
        with pytest.raises(ValueError, match="0.0–1.0"):
            self._valid_prediction(confidence=-0.01)

    def test_day_range_start_after_end_raises(self):
        with pytest.raises(ValueError, match="must be <="):
            self._valid_prediction(high_symptom_day_range=(26, 20))

    def test_is_high_confidence_true(self):
        pred = self._valid_prediction(confidence=0.7)
        assert pred.is_high_confidence is True

    def test_is_high_confidence_false(self):
        pred = self._valid_prediction(confidence=0.69)
        assert pred.is_high_confidence is False

    def test_display_confidence_labels(self):
        assert self._valid_prediction(confidence=0.7).display_confidence == "consistent pattern"
        assert self._valid_prediction(confidence=0.5).display_confidence == "emerging pattern"
        assert self._valid_prediction(confidence=0.2).display_confidence == "variable pattern"


# ---------------------------------------------------------------------------
# PatternResult
# ---------------------------------------------------------------------------

class TestPatternResult:

    def _valid_result(self, **overrides) -> PatternResult:
        defaults = dict(
            id=uuid4(),
            user_id=uuid4(),
            generated_at=datetime.utcnow(),
            cycles_analyzed=1,
            total_logs=30,
            symptom_onset_range=(18, 24),
            escalation_speed=EscalationSpeed.MODERATE,
            symptom_clusters=[],
            phase_patterns=[],
            severity_trend=SeverityTrend.STABLE,
            prediction=None,
        )
        defaults.update(overrides)
        return PatternResult(**defaults)

    def test_valid_construction(self):
        result = self._valid_result()
        assert result.total_logs == 30

    def test_negative_cycles_analyzed_raises(self):
        with pytest.raises(ValueError, match="cannot be negative"):
            self._valid_result(cycles_analyzed=-1)

    def test_negative_total_logs_raises(self):
        with pytest.raises(ValueError, match="cannot be negative"):
            self._valid_result(total_logs=-1)

    def test_invalid_onset_range_raises(self):
        with pytest.raises(ValueError, match="must be <="):
            self._valid_result(symptom_onset_range=(25, 18))

    def test_has_prediction_false_when_none(self):
        result = self._valid_result(prediction=None)
        assert result.has_prediction is False

    def test_has_prediction_true_when_set(self):
        pred = CyclePrediction(
            high_symptom_day_range=(20, 26),
            predicted_dominant_phase=CyclePhase.LUTEAL,
            confidence=0.65,
            basis_cycles=2,
        )
        result = self._valid_result(prediction=pred)
        assert result.has_prediction is True

    def test_most_burdensome_phase_none_when_no_patterns(self):
        result = self._valid_result(phase_patterns=[])
        assert result.most_burdensome_phase is None

    def test_most_burdensome_phase_returns_highest_pain(self):
        low_pain = PhasePattern(
            phase=CyclePhase.FOLLICULAR,
            onset_day_range=(6, 13),
            average_pain=2.0,
            average_energy=7.0,
            dominant_symptoms=[],
            severity_trend=SeverityTrend.STABLE,
            log_count=8,
        )
        high_pain = PhasePattern(
            phase=CyclePhase.LUTEAL,
            onset_day_range=(18, 28),
            average_pain=7.5,
            average_energy=3.0,
            dominant_symptoms=[Symptom.PELVIC_PAIN],
            severity_trend=SeverityTrend.ESCALATING,
            log_count=11,
        )
        result = self._valid_result(phase_patterns=[low_pain, high_pain])
        assert result.most_burdensome_phase == high_pain

    def test_notable_clusters_filters_by_threshold(self):
        notable = SymptomCluster(
            symptoms=frozenset({Symptom.MOOD_CRASH, Symptom.BRAIN_FOG}),
            typical_phase=CyclePhase.LUTEAL,
            occurrence_rate=0.5,
        )
        not_notable = SymptomCluster(
            symptoms=frozenset({Symptom.PELVIC_PAIN, Symptom.BLOATING}),
            typical_phase=CyclePhase.MENSTRUAL,
            occurrence_rate=0.1,
        )
        result = self._valid_result(symptom_clusters=[notable, not_notable])
        assert result.notable_clusters == [notable]


# ---------------------------------------------------------------------------
# EarlyFeedback
# ---------------------------------------------------------------------------

class TestEarlyFeedback:

    def test_valid_construction(self):
        fb = EarlyFeedback(
            user_id=uuid4(),
            message="You tend to log higher pain around this point in your cycle.",
            generated_at=datetime.utcnow(),
            log_count=7,
            trigger_phase=CyclePhase.LUTEAL,
        )
        assert fb.log_count == 7

    def test_empty_message_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            EarlyFeedback(
                user_id=uuid4(),
                message="",
                generated_at=datetime.utcnow(),
                log_count=7,
            )

    def test_whitespace_message_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            EarlyFeedback(
                user_id=uuid4(),
                message="   ",
                generated_at=datetime.utcnow(),
                log_count=7,
            )

    def test_insufficient_logs_raises(self):
        with pytest.raises(ValueError, match="at least"):
            EarlyFeedback(
                user_id=uuid4(),
                message="Some observation.",
                generated_at=datetime.utcnow(),
                log_count=2,
            )

    def test_trigger_phase_is_optional(self):
        fb = EarlyFeedback(
            user_id=uuid4(),
            message="You've been consistent. That's building a clearer picture.",
            generated_at=datetime.utcnow(),
            log_count=5,
            trigger_phase=None,
        )
        assert fb.trigger_phase is None
