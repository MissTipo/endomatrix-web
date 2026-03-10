"""
Contract tests for domain ports.

These tests run against the in-memory fakes and verify that any
implementation of a port satisfies its contract correctly.

When you build the real PostgresLogRepository, you run these same
tests against it. If they pass, the real implementation is correct.
This is the value of the ports pattern — the contract is explicit
and machine-verifiable.
"""

import pytest
from datetime import date, datetime, timedelta
from uuid import uuid4

from domain.models.cycle import CycleBaseline, CyclePhase, Score
from domain.models.daily_log import DailyLog
from domain.models.events import LogCreated
from domain.models.pattern import (
    EarlyFeedback,
    EscalationSpeed,
    PatternResult,
    SeverityTrend,
)
from domain.models.symptom import Symptom
from tests.fakes import (
    InMemoryCycleRepository,
    InMemoryEventPublisher,
    InMemoryLogRepository,
    InMemoryPatternRepository,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_log(user_id, logged_date, cycle_day=14, phase=CyclePhase.FOLLICULAR) -> DailyLog:
    return DailyLog(
        id=uuid4(),
        user_id=user_id,
        logged_date=logged_date,
        pain_level=Score(4),
        energy_level=Score(6),
        dominant_symptom=Symptom.PELVIC_PAIN,
        cycle_day=cycle_day,
        cycle_phase=phase,
        created_at=datetime.utcnow(),
    )


def make_baseline(user_id) -> CycleBaseline:
    return CycleBaseline(
        user_id=user_id,
        last_period_start=date.today() - timedelta(days=10),
        average_cycle_length=28,
        is_irregular=False,
        updated_at=datetime.utcnow(),
    )


def make_pattern(user_id) -> PatternResult:
    return PatternResult(
        id=uuid4(),
        user_id=user_id,
        generated_at=datetime.utcnow(),
        cycles_analyzed=1,
        total_logs=30,
        symptom_onset_range=(18, 24),
        escalation_speed=EscalationSpeed.MODERATE,
        symptom_clusters=[],
        phase_patterns=[],
        severity_trend=SeverityTrend.STABLE,
    )


# ---------------------------------------------------------------------------
# ILogRepository contract
# ---------------------------------------------------------------------------

class TestLogRepositoryContract:

    def setup_method(self):
        self.repo = InMemoryLogRepository()
        self.user_id = uuid4()

    def test_save_and_retrieve_by_id(self):
        log = make_log(self.user_id, date.today())
        self.repo.save(log)
        retrieved = self.repo.get_by_id(log.id)
        assert retrieved == log

    def test_get_by_id_returns_none_for_unknown(self):
        assert self.repo.get_by_id(uuid4()) is None

    def test_get_by_date_returns_correct_log(self):
        log = make_log(self.user_id, date.today())
        self.repo.save(log)
        retrieved = self.repo.get_by_date(self.user_id, date.today())
        assert retrieved == log

    def test_get_by_date_returns_none_when_no_log(self):
        result = self.repo.get_by_date(self.user_id, date.today())
        assert result is None

    def test_superseded_log_is_not_returned_by_date(self):
        original = make_log(self.user_id, date.today())
        self.repo.save(original)
        replacement = make_log(self.user_id, date.today())
        self.repo.save(replacement)
        result = self.repo.get_by_date(self.user_id, date.today())
        assert result == replacement
        assert result.id != original.id

    def test_superseded_log_is_not_returned_by_id(self):
        original = make_log(self.user_id, date.today())
        self.repo.save(original)
        replacement = make_log(self.user_id, date.today())
        self.repo.save(replacement)
        assert self.repo.get_by_id(original.id) is None

    def test_get_logs_for_user_returns_all_active(self):
        for i in range(5):
            log = make_log(self.user_id, date.today() - timedelta(days=i))
            self.repo.save(log)
        logs = self.repo.get_logs_for_user(self.user_id)
        assert len(logs) == 5

    def test_get_logs_for_user_ordered_descending(self):
        for i in range(3):
            self.repo.save(make_log(self.user_id, date.today() - timedelta(days=i)))
        logs = self.repo.get_logs_for_user(self.user_id)
        dates = [l.logged_date for l in logs]
        assert dates == sorted(dates, reverse=True)

    def test_get_logs_for_user_respects_limit(self):
        for i in range(5):
            self.repo.save(make_log(self.user_id, date.today() - timedelta(days=i)))
        logs = self.repo.get_logs_for_user(self.user_id, limit=3)
        assert len(logs) == 3

    def test_get_logs_for_user_excludes_other_users(self):
        other_user = uuid4()
        self.repo.save(make_log(self.user_id, date.today()))
        self.repo.save(make_log(other_user, date.today() - timedelta(days=1)))
        logs = self.repo.get_logs_for_user(self.user_id)
        assert all(l.user_id == self.user_id for l in logs)

    def test_get_logs_in_range_inclusive(self):
        for i in range(7):
            self.repo.save(make_log(self.user_id, date.today() - timedelta(days=i)))
        start = date.today() - timedelta(days=4)
        end = date.today() - timedelta(days=1)
        logs = self.repo.get_logs_in_range(self.user_id, start, end)
        assert len(logs) == 4
        assert all(start <= l.logged_date <= end for l in logs)

    def test_get_logs_in_range_ordered_ascending(self):
        for i in range(5):
            self.repo.save(make_log(self.user_id, date.today() - timedelta(days=i)))
        start = date.today() - timedelta(days=4)
        end = date.today()
        logs = self.repo.get_logs_in_range(self.user_id, start, end)
        dates = [l.logged_date for l in logs]
        assert dates == sorted(dates)

    def test_get_logs_by_phase(self):
        luteal = make_log(self.user_id, date.today(), phase=CyclePhase.LUTEAL)
        follicular = make_log(
            self.user_id, date.today() - timedelta(days=1), phase=CyclePhase.FOLLICULAR
        )
        self.repo.save(luteal)
        self.repo.save(follicular)
        logs = self.repo.get_logs_by_phase(self.user_id, CyclePhase.LUTEAL)
        assert len(logs) == 1
        assert logs[0].cycle_phase == CyclePhase.LUTEAL

    def test_count_logs_for_user(self):
        for i in range(4):
            self.repo.save(make_log(self.user_id, date.today() - timedelta(days=i)))
        assert self.repo.count_logs_for_user(self.user_id) == 4

    def test_count_excludes_other_users(self):
        self.repo.save(make_log(self.user_id, date.today()))
        self.repo.save(make_log(uuid4(), date.today() - timedelta(days=1)))
        assert self.repo.count_logs_for_user(self.user_id) == 1

    def test_has_log_for_date_true(self):
        self.repo.save(make_log(self.user_id, date.today()))
        assert self.repo.has_log_for_date(self.user_id, date.today()) is True

    def test_has_log_for_date_false(self):
        assert self.repo.has_log_for_date(self.user_id, date.today()) is False

    def test_get_most_recent_log(self):
        older = make_log(self.user_id, date.today() - timedelta(days=3))
        newer = make_log(self.user_id, date.today())
        self.repo.save(older)
        self.repo.save(newer)
        result = self.repo.get_most_recent_log(self.user_id)
        assert result == newer

    def test_get_most_recent_log_none_when_empty(self):
        assert self.repo.get_most_recent_log(self.user_id) is None


# ---------------------------------------------------------------------------
# ICycleRepository contract
# ---------------------------------------------------------------------------

class TestCycleRepositoryContract:

    def setup_method(self):
        self.repo = InMemoryCycleRepository()
        self.user_id = uuid4()

    def test_save_and_retrieve(self):
        baseline = make_baseline(self.user_id)
        self.repo.save(baseline)
        retrieved = self.repo.get_by_user_id(self.user_id)
        assert retrieved == baseline

    def test_get_by_user_id_returns_none_when_missing(self):
        assert self.repo.get_by_user_id(self.user_id) is None

    def test_save_overwrites_existing(self):
        original = make_baseline(self.user_id)
        self.repo.save(original)
        updated = CycleBaseline(
            user_id=self.user_id,
            last_period_start=date.today() - timedelta(days=2),
            average_cycle_length=30,
            is_irregular=False,
            updated_at=datetime.utcnow(),
        )
        self.repo.save(updated)
        result = self.repo.get_by_user_id(self.user_id)
        assert result.average_cycle_length == 30

    def test_exists_true_after_save(self):
        self.repo.save(make_baseline(self.user_id))
        assert self.repo.exists(self.user_id) is True

    def test_exists_false_before_save(self):
        assert self.repo.exists(self.user_id) is False


# ---------------------------------------------------------------------------
# IPatternRepository contract
# ---------------------------------------------------------------------------

class TestPatternRepositoryContract:

    def setup_method(self):
        self.repo = InMemoryPatternRepository()
        self.user_id = uuid4()

    def test_save_and_retrieve_latest(self):
        pattern = make_pattern(self.user_id)
        self.repo.save_pattern(pattern)
        result = self.repo.get_latest_pattern(self.user_id)
        assert result == pattern

    def test_get_latest_returns_most_recent(self):
        older = PatternResult(
            id=uuid4(),
            user_id=self.user_id,
            generated_at=datetime.utcnow() - timedelta(days=30),
            cycles_analyzed=1,
            total_logs=30,
            symptom_onset_range=(18, 24),
            escalation_speed=EscalationSpeed.MODERATE,
            symptom_clusters=[],
            phase_patterns=[],
            severity_trend=SeverityTrend.STABLE,
        )
        newer = make_pattern(self.user_id)
        self.repo.save_pattern(older)
        self.repo.save_pattern(newer)
        result = self.repo.get_latest_pattern(self.user_id)
        assert result == newer

    def test_get_latest_returns_none_when_empty(self):
        assert self.repo.get_latest_pattern(self.user_id) is None

    def test_get_all_patterns_ordered_descending(self):
        for i in range(3):
            p = PatternResult(
                id=uuid4(),
                user_id=self.user_id,
                generated_at=datetime.utcnow() - timedelta(days=i * 30),
                cycles_analyzed=1,
                total_logs=30,
                symptom_onset_range=(18, 24),
                escalation_speed=EscalationSpeed.MODERATE,
                symptom_clusters=[],
                phase_patterns=[],
                severity_trend=SeverityTrend.STABLE,
            )
            self.repo.save_pattern(p)
        patterns = self.repo.get_all_patterns(self.user_id)
        dates = [p.generated_at for p in patterns]
        assert dates == sorted(dates, reverse=True)

    def test_count_patterns(self):
        for _ in range(3):
            self.repo.save_pattern(make_pattern(self.user_id))
        assert self.repo.count_patterns(self.user_id) == 3

    def test_save_and_retrieve_latest_feedback(self):
        fb = EarlyFeedback(
            user_id=self.user_id,
            message="You tend to log higher pain around this point.",
            generated_at=datetime.utcnow(),
            log_count=7,
        )
        self.repo.save_feedback(fb)
        result = self.repo.get_latest_feedback(self.user_id)
        assert result == fb

    def test_get_latest_feedback_returns_none_when_empty(self):
        assert self.repo.get_latest_feedback(self.user_id) is None


# ---------------------------------------------------------------------------
# IEventPublisher contract
# ---------------------------------------------------------------------------

class TestEventPublisherContract:

    def setup_method(self):
        self.publisher = InMemoryEventPublisher()
        self.user_id = uuid4()

    def test_publish_single_event(self):
        event = LogCreated(
            user_id=self.user_id,
            occurred_at=datetime.utcnow(),
            log_id=uuid4(),
            logged_date=str(date.today()),
            cycle_phase=CyclePhase.FOLLICULAR,
            pain_level=4,
            energy_level=6,
        )
        self.publisher.publish(event)
        assert len(self.publisher.events) == 1

    def test_publish_all_events(self):
        events = [
            LogCreated(
                user_id=self.user_id,
                occurred_at=datetime.utcnow(),
                log_id=uuid4(),
                logged_date=str(date.today() - timedelta(days=i)),
                cycle_phase=CyclePhase.FOLLICULAR,
                pain_level=4,
                energy_level=6,
            )
            for i in range(3)
        ]
        self.publisher.publish_all(events)
        assert len(self.publisher.events) == 3

    def test_of_type_filters_correctly(self):
        event = LogCreated(
            user_id=self.user_id,
            occurred_at=datetime.utcnow(),
            log_id=uuid4(),
            logged_date=str(date.today()),
            cycle_phase=CyclePhase.FOLLICULAR,
            pain_level=4,
            energy_level=6,
        )
        self.publisher.publish(event)
        matches = self.publisher.of_type(LogCreated)
        assert len(matches) == 1

    def test_clear_resets_events(self):
        event = LogCreated(
            user_id=self.user_id,
            occurred_at=datetime.utcnow(),
            log_id=uuid4(),
            logged_date=str(date.today()),
            cycle_phase=CyclePhase.FOLLICULAR,
            pain_level=4,
            energy_level=6,
        )
        self.publisher.publish(event)
        self.publisher.clear()
        assert len(self.publisher.events) == 0
