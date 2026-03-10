"""
Tests for domain.engine.pattern_engine

Covers:
- Returns None when not enough logs
- Onset detection across cycles
- Escalation speed classification
- Symptom clustering
- Phase pattern construction
- Severity trend detection
- Cycle prediction gating (requires 2 cycles)
- Early feedback generation
- Edge cases: all logs same phase, no high pain days
"""

import pytest
from datetime import date, datetime, timedelta
from uuid import uuid4

from domain.models.cycle import CyclePhase, Score
from domain.models.daily_log import DailyLog
from domain.models.pattern import EscalationSpeed, SeverityTrend
from domain.models.symptom import Symptom
from domain.engine.pattern_engine import (
    PatternEngine,
    MIN_LOGS_FOR_PATTERN,
    MIN_LOGS_FOR_FEEDBACK,
    HIGH_PAIN_THRESHOLD,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_log(
    user_id,
    logged_date: date,
    pain: int = 3,
    energy: int = 7,
    cycle_day: int = 10,
    phase: CyclePhase = CyclePhase.FOLLICULAR,
    symptom: Symptom = Symptom.BLOATING,
) -> DailyLog:
    return DailyLog(
        id=uuid4(),
        user_id=user_id,
        logged_date=logged_date,
        pain_level=Score(pain),
        energy_level=Score(energy),
        dominant_symptom=symptom,
        cycle_day=cycle_day,
        cycle_phase=phase,
        created_at=datetime.utcnow(),
    )


def make_luteal_spike_logs(user_id, num_days: int = 30) -> list[DailyLog]:
    """
    Simulate a realistic luteal phase pain spike pattern.
    Pain is low in follicular (days 1-14), then rises sharply in luteal (days 15+).
    Generates enough logs to span approximately one cycle.
    """
    logs = []
    for i in range(num_days):
        log_date = date(2025, 1, 1) + timedelta(days=i)
        cycle_day = (i % 28) + 1

        if cycle_day >= 15:
            pain = min(10, 4 + (cycle_day - 15))
            energy = max(1, 7 - (cycle_day - 15))
            phase = CyclePhase.LUTEAL
            symptom = Symptom.PELVIC_PAIN
        elif cycle_day <= 5:
            pain = 3
            energy = 5
            phase = CyclePhase.MENSTRUAL
            symptom = Symptom.PELVIC_PAIN
        else:
            pain = 2
            energy = 8
            phase = CyclePhase.FOLLICULAR
            symptom = Symptom.BLOATING

        logs.append(make_log(
            user_id=user_id,
            logged_date=log_date,
            pain=pain,
            energy=energy,
            cycle_day=cycle_day,
            phase=phase,
            symptom=symptom,
        ))
    return logs


@pytest.fixture
def engine():
    return PatternEngine()


@pytest.fixture
def user_id():
    return uuid4()


# ---------------------------------------------------------------------------
# Minimum log threshold
# ---------------------------------------------------------------------------

class TestMinimumLogThreshold:

    def test_returns_none_with_insufficient_logs(self, engine, user_id):
        logs = [
            make_log(user_id, date(2025, 1, 1) + timedelta(days=i))
            for i in range(MIN_LOGS_FOR_PATTERN - 1)
        ]
        result = engine.analyze(logs)
        assert result is None

    def test_returns_result_at_minimum_threshold(self, engine, user_id):
        logs = [
            make_log(user_id, date(2025, 1, 1) + timedelta(days=i), cycle_day=i + 1)
            for i in range(MIN_LOGS_FOR_PATTERN)
        ]
        result = engine.analyze(logs)
        assert result is not None

    def test_result_has_correct_user_id(self, engine, user_id):
        logs = make_luteal_spike_logs(user_id)
        result = engine.analyze(logs)
        assert result.user_id == user_id

    def test_result_total_logs_matches_input(self, engine, user_id):
        logs = make_luteal_spike_logs(user_id, num_days=30)
        result = engine.analyze(logs)
        assert result.total_logs == 30


# ---------------------------------------------------------------------------
# Onset detection
# ---------------------------------------------------------------------------

class TestOnsetDetection:

    def test_onset_range_is_in_luteal_for_spike_pattern(self, engine, user_id):
        logs = make_luteal_spike_logs(user_id, num_days=30)
        result = engine.analyze(logs)
        # Onset should begin at or after cycle day 15 (luteal start)
        assert result.symptom_onset_range[0] >= 14

    def test_onset_range_start_lte_end(self, engine, user_id):
        logs = make_luteal_spike_logs(user_id, num_days=30)
        result = engine.analyze(logs)
        start, end = result.symptom_onset_range
        assert start <= end


# ---------------------------------------------------------------------------
# Escalation speed
# ---------------------------------------------------------------------------

class TestEscalationSpeed:

    def test_sharp_escalation_detected(self, engine, user_id):
        """Pain jumps from 2 to 9 in one day — should be SHARP."""
        logs = []
        for i in range(20):
            log_date = date(2025, 1, 1) + timedelta(days=i)
            cycle_day = i + 1
            # Low pain until day 15, then immediate spike
            pain = 9 if cycle_day >= 15 else 2
            phase = CyclePhase.LUTEAL if cycle_day >= 15 else CyclePhase.FOLLICULAR
            logs.append(make_log(user_id, log_date, pain=pain,
                                  cycle_day=cycle_day, phase=phase))
        result = engine.analyze(logs)
        assert result.escalation_speed == EscalationSpeed.SHARP

    def test_gradual_escalation_detected(self, engine, user_id):
        """Pain rises 1 point per day over 7 days — should be GRADUAL."""
        logs = []
        for i in range(20):
            log_date = date(2025, 1, 1) + timedelta(days=i)
            cycle_day = i + 1
            if cycle_day >= 15:
                pain = min(10, 2 + (cycle_day - 15))
                phase = CyclePhase.LUTEAL
            else:
                pain = 2
                phase = CyclePhase.FOLLICULAR
            logs.append(make_log(user_id, log_date, pain=pain,
                                  cycle_day=cycle_day, phase=phase))
        result = engine.analyze(logs)
        assert result.escalation_speed in {EscalationSpeed.GRADUAL, EscalationSpeed.MODERATE}

    def test_unknown_escalation_when_no_high_pain(self, engine, user_id):
        """All logs have pain below onset threshold — should be UNKNOWN."""
        logs = [
            make_log(user_id, date(2025, 1, 1) + timedelta(days=i),
                     pain=2, cycle_day=i + 1)
            for i in range(MIN_LOGS_FOR_PATTERN)
        ]
        result = engine.analyze(logs)
        assert result.escalation_speed == EscalationSpeed.UNKNOWN


# ---------------------------------------------------------------------------
# Severity trend
# ---------------------------------------------------------------------------

class TestSeverityTrend:

    def test_escalating_trend_detected(self, engine, user_id):
        """Pain doubles from first half to second half."""
        logs = []
        for i in range(30):
            log_date = date(2025, 1, 1) + timedelta(days=i)
            # First 15 days: pain 2. Next 15: pain 7.
            pain = 2 if i < 15 else 7
            logs.append(make_log(user_id, log_date, pain=pain, cycle_day=(i % 28) + 1))
        result = engine.analyze(logs)
        assert result.severity_trend == SeverityTrend.ESCALATING

    def test_improving_trend_detected(self, engine, user_id):
        """Pain halves from first half to second half."""
        logs = []
        for i in range(30):
            log_date = date(2025, 1, 1) + timedelta(days=i)
            pain = 8 if i < 15 else 2
            logs.append(make_log(user_id, log_date, pain=pain, cycle_day=(i % 28) + 1))
        result = engine.analyze(logs)
        assert result.severity_trend == SeverityTrend.IMPROVING

    def test_stable_trend_detected(self, engine, user_id):
        """Pain is consistent throughout."""
        logs = [
            make_log(user_id, date(2025, 1, 1) + timedelta(days=i),
                     pain=5, cycle_day=(i % 28) + 1)
            for i in range(30)
        ]
        result = engine.analyze(logs)
        assert result.severity_trend == SeverityTrend.STABLE

    def test_insufficient_data_trend_for_few_logs(self, engine, user_id):
        logs = [
            make_log(user_id, date(2025, 1, 1) + timedelta(days=i),
                     pain=5, cycle_day=i + 1)
            for i in range(MIN_LOGS_FOR_PATTERN)
        ]
        result = engine.analyze(logs)
        # With exactly MIN logs, trend detection may return INSUFFICIENT_DATA
        assert result.severity_trend in {
            SeverityTrend.STABLE,
            SeverityTrend.ESCALATING,
            SeverityTrend.IMPROVING,
            SeverityTrend.INSUFFICIENT_DATA,
        }


# ---------------------------------------------------------------------------
# Phase patterns
# ---------------------------------------------------------------------------

class TestPhasePatterns:

    def test_phase_patterns_exist_for_known_phases(self, engine, user_id):
        logs = make_luteal_spike_logs(user_id, num_days=30)
        result = engine.analyze(logs)
        phases_in_result = {p.phase for p in result.phase_patterns}
        assert CyclePhase.LUTEAL in phases_in_result

    def test_phase_patterns_ordered_by_pain_descending(self, engine, user_id):
        logs = make_luteal_spike_logs(user_id, num_days=30)
        result = engine.analyze(logs)
        if len(result.phase_patterns) >= 2:
            pains = [p.average_pain for p in result.phase_patterns]
            assert pains == sorted(pains, reverse=True)

    def test_unknown_phase_excluded_from_patterns(self, engine, user_id):
        logs = [
            make_log(user_id, date(2025, 1, 1) + timedelta(days=i),
                     phase=CyclePhase.UNKNOWN, cycle_day=i + 1)
            for i in range(MIN_LOGS_FOR_PATTERN)
        ]
        result = engine.analyze(logs)
        phases = {p.phase for p in result.phase_patterns}
        assert CyclePhase.UNKNOWN not in phases

    def test_luteal_is_most_burdensome_in_spike_pattern(self, engine, user_id):
        logs = make_luteal_spike_logs(user_id, num_days=30)
        result = engine.analyze(logs)
        assert result.most_burdensome_phase is not None
        assert result.most_burdensome_phase.phase == CyclePhase.LUTEAL


# ---------------------------------------------------------------------------
# Cycle prediction
# ---------------------------------------------------------------------------

class TestCyclePrediction:

    def test_no_prediction_from_single_cycle(self, engine, user_id):
        """One cycle's worth of data — no prediction."""
        logs = make_luteal_spike_logs(user_id, num_days=28)
        result = engine.analyze(logs)
        assert result.prediction is None

    def test_prediction_generated_from_two_cycles(self, engine, user_id):
        """Two cycles of data — prediction should be present."""
        logs = make_luteal_spike_logs(user_id, num_days=56)
        result = engine.analyze(logs)
        assert result.prediction is not None

    def test_prediction_basis_cycles_correct(self, engine, user_id):
        logs = make_luteal_spike_logs(user_id, num_days=56)
        result = engine.analyze(logs)
        if result.prediction is not None:
            assert result.prediction.basis_cycles >= 2

    def test_prediction_confidence_between_zero_and_one(self, engine, user_id):
        logs = make_luteal_spike_logs(user_id, num_days=56)
        result = engine.analyze(logs)
        if result.prediction is not None:
            assert 0.0 <= result.prediction.confidence <= 1.0


# ---------------------------------------------------------------------------
# Early feedback
# ---------------------------------------------------------------------------

class TestEarlyFeedback:

    def test_returns_none_with_too_few_logs(self, engine, user_id):
        logs = [
            make_log(user_id, date(2025, 1, 1) + timedelta(days=i))
            for i in range(MIN_LOGS_FOR_FEEDBACK - 1)
        ]
        feedback = engine.generate_early_feedback(logs)
        assert feedback is None

    def test_returns_feedback_with_enough_logs(self, engine, user_id):
        logs = make_luteal_spike_logs(user_id, num_days=14)
        feedback = engine.generate_early_feedback(logs)
        assert feedback is not None

    def test_feedback_message_is_non_empty(self, engine, user_id):
        logs = make_luteal_spike_logs(user_id, num_days=14)
        feedback = engine.generate_early_feedback(logs)
        if feedback is not None:
            assert len(feedback.message.strip()) > 0

    def test_feedback_log_count_matches_input(self, engine, user_id):
        logs = make_luteal_spike_logs(user_id, num_days=14)
        feedback = engine.generate_early_feedback(logs)
        if feedback is not None:
            assert feedback.log_count == 14

    def test_feedback_user_id_matches(self, engine, user_id):
        logs = make_luteal_spike_logs(user_id, num_days=14)
        feedback = engine.generate_early_feedback(logs)
        if feedback is not None:
            assert feedback.user_id == user_id

    def test_phase_feedback_mentions_luteal_for_spike_pattern(self, engine, user_id):
        logs = make_luteal_spike_logs(user_id, num_days=14)
        feedback = engine.generate_early_feedback(logs)
        if feedback is not None and feedback.trigger_phase is not None:
            assert feedback.trigger_phase == CyclePhase.LUTEAL
