"""
Tests for application use cases.

These tests use only in-memory fakes. No database, no HTTP, no real engine
unless explicitly testing integration with the pattern engine.

Each test class covers one use case. The setup_method builds the use case
with fresh fakes on every test so there is no state leakage between tests.
"""

import pytest
from datetime import date, datetime, timedelta
from uuid import uuid4

from application.use_cases import (
    GenerateEarlyFeedback,
    GenerateEarlyFeedbackCommand,
    GeneratePattern,
    GeneratePatternCommand,
    GetHomeState,
    GetHomeStateCommand,
    GetPatternSummary,
    GetPatternSummaryCommand,
    INSIGHT_UNLOCK_THRESHOLD,
    LogDailyEntry,
    LogDailyEntryCommand,
    SetCycleBaseline,
    SetCycleBaselineCommand,
    UpdateCycleBaseline,
    UpdateCycleBaselineCommand,
)
from domain.models.cycle import CyclePhase, Score
from domain.models.daily_log import DailyLog
from domain.models.events import (
    CycleBaselineSet,
    CycleBaselineUpdated,
    EarlyFeedbackGenerated,
    LogCreated,
    LogSuperseded,
    PatternGenerated,
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

def make_baseline_command(user_id, days_ago: int = 10):
    return SetCycleBaselineCommand(
        user_id=user_id,
        last_period_start=date.today() - timedelta(days=days_ago),
        average_cycle_length=28,
        is_irregular=False,
    )


def make_log_command(user_id, days_ago: int = 0):
    return LogDailyEntryCommand(
        user_id=user_id,
        logged_date=date.today() - timedelta(days=days_ago),
        pain_level=4,
        energy_level=6,
        dominant_symptom=Symptom.PELVIC_PAIN,
    )


def make_log_directly(
    user_id, logged_date, cycle_day=14, phase=CyclePhase.FOLLICULAR, pain=4
) -> DailyLog:
    return DailyLog(
        id=uuid4(),
        user_id=user_id,
        logged_date=logged_date,
        pain_level=Score(pain),
        energy_level=Score(6),
        dominant_symptom=Symptom.PELVIC_PAIN,
        cycle_day=cycle_day,
        cycle_phase=phase,
        created_at=datetime.utcnow(),
    )


# ---------------------------------------------------------------------------
# SetCycleBaseline
# ---------------------------------------------------------------------------

class TestSetCycleBaseline:

    def setup_method(self):
        self.cycle_repo = InMemoryCycleRepository()
        self.publisher = InMemoryEventPublisher()
        self.use_case = SetCycleBaseline(self.cycle_repo, self.publisher)
        self.user_id = uuid4()

    def test_saves_baseline(self):
        self.use_case.execute(make_baseline_command(self.user_id))
        assert self.cycle_repo.exists(self.user_id)

    def test_returns_baseline_in_result(self):
        result = self.use_case.execute(make_baseline_command(self.user_id))
        assert result.baseline.user_id == self.user_id

    def test_publishes_baseline_set_event(self):
        self.use_case.execute(make_baseline_command(self.user_id))
        events = self.publisher.of_type(CycleBaselineSet)
        assert len(events) == 1

    def test_raises_if_baseline_already_exists(self):
        self.use_case.execute(make_baseline_command(self.user_id))
        with pytest.raises(ValueError, match="already exists"):
            self.use_case.execute(make_baseline_command(self.user_id))

    def test_irregular_cycle_with_no_length(self):
        cmd = SetCycleBaselineCommand(
            user_id=self.user_id,
            last_period_start=date.today() - timedelta(days=5),
            average_cycle_length=None,
            is_irregular=True,
        )
        result = self.use_case.execute(cmd)
        assert result.baseline.is_irregular is True
        assert result.baseline.average_cycle_length is None


# ---------------------------------------------------------------------------
# UpdateCycleBaseline
# ---------------------------------------------------------------------------

class TestUpdateCycleBaseline:

    def setup_method(self):
        self.cycle_repo = InMemoryCycleRepository()
        self.publisher = InMemoryEventPublisher()
        self.set_uc = SetCycleBaseline(self.cycle_repo, self.publisher)
        self.update_uc = UpdateCycleBaseline(self.cycle_repo, self.publisher)
        self.user_id = uuid4()

    def test_updates_existing_baseline(self):
        self.set_uc.execute(make_baseline_command(self.user_id))
        cmd = UpdateCycleBaselineCommand(
            user_id=self.user_id,
            last_period_start=date.today() - timedelta(days=3),
            average_cycle_length=30,
            is_irregular=False,
        )
        self.update_uc.execute(cmd)
        updated = self.cycle_repo.get_by_user_id(self.user_id)
        assert updated.average_cycle_length == 30

    def test_publishes_updated_event(self):
        self.set_uc.execute(make_baseline_command(self.user_id))
        self.publisher.clear()
        cmd = UpdateCycleBaselineCommand(
            user_id=self.user_id,
            last_period_start=date.today() - timedelta(days=3),
            average_cycle_length=30,
            is_irregular=False,
        )
        self.update_uc.execute(cmd)
        events = self.publisher.of_type(CycleBaselineUpdated)
        assert len(events) == 1

    def test_raises_if_no_baseline_exists(self):
        cmd = UpdateCycleBaselineCommand(
            user_id=self.user_id,
            last_period_start=date.today() - timedelta(days=3),
            average_cycle_length=30,
            is_irregular=False,
        )
        with pytest.raises(ValueError, match="No cycle baseline found"):
            self.update_uc.execute(cmd)

    def test_updated_event_records_previous_values(self):
        self.set_uc.execute(make_baseline_command(self.user_id, days_ago=10))
        self.publisher.clear()
        cmd = UpdateCycleBaselineCommand(
            user_id=self.user_id,
            last_period_start=date.today() - timedelta(days=3),
            average_cycle_length=32,
            is_irregular=False,
        )
        self.update_uc.execute(cmd)
        event = self.publisher.of_type(CycleBaselineUpdated)[0]
        assert event.previous_cycle_length == 28
        assert event.new_cycle_length == 32


# ---------------------------------------------------------------------------
# LogDailyEntry
# ---------------------------------------------------------------------------

class TestLogDailyEntry:

    def setup_method(self):
        self.log_repo = InMemoryLogRepository()
        self.cycle_repo = InMemoryCycleRepository()
        self.publisher = InMemoryEventPublisher()
        self.set_baseline = SetCycleBaseline(self.cycle_repo, self.publisher)
        self.use_case = LogDailyEntry(self.log_repo, self.cycle_repo, self.publisher)
        self.user_id = uuid4()
        # Set up baseline for all tests
        self.set_baseline.execute(make_baseline_command(self.user_id))
        self.publisher.clear()

    def test_saves_log(self):
        self.use_case.execute(make_log_command(self.user_id))
        assert self.log_repo.count_logs_for_user(self.user_id) == 1

    def test_returns_log_in_result(self):
        result = self.use_case.execute(make_log_command(self.user_id))
        assert result.log.user_id == self.user_id

    def test_publishes_log_created_event(self):
        self.use_case.execute(make_log_command(self.user_id))
        assert len(self.publisher.of_type(LogCreated)) == 1

    def test_log_has_inferred_cycle_phase(self):
        result = self.use_case.execute(make_log_command(self.user_id))
        assert result.log.cycle_phase != CyclePhase.UNKNOWN

    def test_log_has_inferred_cycle_day(self):
        result = self.use_case.execute(make_log_command(self.user_id))
        assert result.log.cycle_day >= 1

    def test_raises_without_baseline(self):
        no_baseline_user = uuid4()
        cmd = make_log_command(no_baseline_user)
        with pytest.raises(ValueError, match="No cycle baseline"):
            self.use_case.execute(cmd)

    def test_supersedes_existing_log_for_same_date(self):
        cmd = make_log_command(self.user_id, days_ago=0)
        self.use_case.execute(cmd)
        self.publisher.clear()

        # Submit a second log for the same date
        result = self.use_case.execute(cmd)
        assert result.was_superseded is True
        assert len(self.publisher.of_type(LogSuperseded)) == 1
        assert len(self.publisher.of_type(LogCreated)) == 1

    def test_count_after_supersession_is_still_one(self):
        cmd = make_log_command(self.user_id, days_ago=0)
        self.use_case.execute(cmd)
        self.use_case.execute(cmd)
        assert self.log_repo.count_logs_for_user(self.user_id) == 1

    def test_insight_threshold_crossed_at_exactly_30(self):
        # Submit 29 logs on previous days
        for i in range(1, 30):
            self.use_case.execute(make_log_command(self.user_id, days_ago=i))
        self.publisher.clear()

        # 30th log
        result = self.use_case.execute(make_log_command(self.user_id, days_ago=0))
        assert result.insight_threshold_crossed is True

    def test_insight_threshold_not_crossed_before_30(self):
        result = self.use_case.execute(make_log_command(self.user_id))
        assert result.insight_threshold_crossed is False

    def test_mood_level_stored_when_provided(self):
        cmd = LogDailyEntryCommand(
            user_id=self.user_id,
            logged_date=date.today(),
            pain_level=4,
            energy_level=6,
            dominant_symptom=Symptom.PELVIC_PAIN,
            mood_level=7,
        )
        result = self.use_case.execute(cmd)
        assert result.log.mood_level == Score(7)

    def test_note_stored_when_provided(self):
        cmd = LogDailyEntryCommand(
            user_id=self.user_id,
            logged_date=date.today(),
            pain_level=4,
            energy_level=6,
            dominant_symptom=Symptom.PELVIC_PAIN,
            note="Rough morning.",
        )
        result = self.use_case.execute(cmd)
        assert result.log.note == "Rough morning."


# ---------------------------------------------------------------------------
# GeneratePattern
# ---------------------------------------------------------------------------

class TestGeneratePattern:

    def setup_method(self):
        self.log_repo = InMemoryLogRepository()
        self.pattern_repo = InMemoryPatternRepository()
        self.publisher = InMemoryEventPublisher()
        self.use_case = GeneratePattern(
            self.log_repo, self.pattern_repo, self.publisher
        )
        self.user_id = uuid4()

    def _seed_logs(self, count: int):
        for i in range(count):
            log = make_log_directly(
                self.user_id,
                date.today() - timedelta(days=count - i),
                cycle_day=(i % 28) + 1,
                phase=CyclePhase.LUTEAL if (i % 28) >= 14 else CyclePhase.FOLLICULAR,
                pain=7 if (i % 28) >= 14 else 2,
            )
            self.log_repo.save(log)

    def test_returns_not_generated_with_insufficient_logs(self):
        self._seed_logs(5)
        result = self.use_case.execute(GeneratePatternCommand(user_id=self.user_id))
        assert result.was_generated is False
        assert result.pattern is None

    def test_generates_pattern_with_sufficient_logs(self):
        self._seed_logs(30)
        result = self.use_case.execute(GeneratePatternCommand(user_id=self.user_id))
        assert result.was_generated is True
        assert result.pattern is not None

    def test_saves_pattern_to_repository(self):
        self._seed_logs(30)
        self.use_case.execute(GeneratePatternCommand(user_id=self.user_id))
        assert self.pattern_repo.count_patterns(self.user_id) == 1

    def test_publishes_pattern_generated_event(self):
        self._seed_logs(30)
        self.use_case.execute(GeneratePatternCommand(user_id=self.user_id))
        assert len(self.publisher.of_type(PatternGenerated)) == 1

    def test_first_pattern_flag_true_on_first_generation(self):
        self._seed_logs(30)
        result = self.use_case.execute(GeneratePatternCommand(user_id=self.user_id))
        assert result.is_first_pattern is True

    def test_first_pattern_flag_false_on_subsequent(self):
        self._seed_logs(30)
        self.use_case.execute(GeneratePatternCommand(user_id=self.user_id))
        result = self.use_case.execute(GeneratePatternCommand(user_id=self.user_id))
        assert result.is_first_pattern is False


# ---------------------------------------------------------------------------
# GetPatternSummary
# ---------------------------------------------------------------------------

class TestGetPatternSummary:

    def setup_method(self):
        self.log_repo = InMemoryLogRepository()
        self.pattern_repo = InMemoryPatternRepository()
        self.publisher = InMemoryEventPublisher()
        self.generate_uc = GeneratePattern(
            self.log_repo, self.pattern_repo, self.publisher
        )
        self.use_case = GetPatternSummary(self.log_repo, self.pattern_repo)
        self.user_id = uuid4()

    def _seed_logs(self, count):
        for i in range(count):
            log = make_log_directly(
                self.user_id,
                date.today() - timedelta(days=count - i),
                cycle_day=(i % 28) + 1,
                phase=CyclePhase.LUTEAL if (i % 28) >= 14 else CyclePhase.FOLLICULAR,
                pain=7 if (i % 28) >= 14 else 2,
            )
            self.log_repo.save(log)

    def test_not_unlocked_before_threshold(self):
        self._seed_logs(10)
        result = self.use_case.execute(GetPatternSummaryCommand(user_id=self.user_id))
        assert result.is_unlocked is False

    def test_logs_until_unlock_decrements(self):
        self._seed_logs(10)
        result = self.use_case.execute(GetPatternSummaryCommand(user_id=self.user_id))
        assert result.logs_until_unlock == INSIGHT_UNLOCK_THRESHOLD - 10

    def test_unlocked_after_threshold_and_pattern_generated(self):
        self._seed_logs(30)
        self.generate_uc.execute(GeneratePatternCommand(user_id=self.user_id))
        result = self.use_case.execute(GetPatternSummaryCommand(user_id=self.user_id))
        assert result.is_unlocked is True
        assert result.pattern is not None

    def test_not_unlocked_if_threshold_met_but_no_pattern(self):
        # Logs exist but GeneratePattern was never called
        self._seed_logs(30)
        result = self.use_case.execute(GetPatternSummaryCommand(user_id=self.user_id))
        assert result.is_unlocked is False


# ---------------------------------------------------------------------------
# GetHomeState
# ---------------------------------------------------------------------------

class TestGetHomeState:

    def setup_method(self):
        self.log_repo = InMemoryLogRepository()
        self.cycle_repo = InMemoryCycleRepository()
        self.pattern_repo = InMemoryPatternRepository()
        self.publisher = InMemoryEventPublisher()
        self.set_baseline = SetCycleBaseline(self.cycle_repo, self.publisher)
        self.use_case = GetHomeState(
            self.log_repo, self.cycle_repo, self.pattern_repo
        )
        self.user_id = uuid4()
        self.set_baseline.execute(make_baseline_command(self.user_id))

    def test_has_not_logged_today_initially(self):
        state = self.use_case.execute(
            GetHomeStateCommand(user_id=self.user_id, today=date.today())
        )
        assert state.has_logged_today is False

    def test_has_logged_today_after_log(self):
        log = make_log_directly(self.user_id, date.today())
        self.log_repo.save(log)
        state = self.use_case.execute(
            GetHomeStateCommand(user_id=self.user_id, today=date.today())
        )
        assert state.has_logged_today is True

    def test_streak_counts_consecutive_days(self):
        for i in range(3):
            log = make_log_directly(self.user_id, date.today() - timedelta(days=i))
            self.log_repo.save(log)
        state = self.use_case.execute(
            GetHomeStateCommand(user_id=self.user_id, today=date.today())
        )
        assert state.streak == 3

    def test_streak_breaks_on_missing_day(self):
        # Log today and 2 days ago, but not yesterday
        self.log_repo.save(make_log_directly(self.user_id, date.today()))
        self.log_repo.save(make_log_directly(
            self.user_id, date.today() - timedelta(days=2)
        ))
        state = self.use_case.execute(
            GetHomeStateCommand(user_id=self.user_id, today=date.today())
        )
        assert state.streak == 1

    def test_phase_inferred_when_baseline_exists(self):
        state = self.use_case.execute(
            GetHomeStateCommand(user_id=self.user_id, today=date.today())
        )
        assert state.current_cycle_day is not None
        assert state.current_phase is not None

    def test_no_phase_without_baseline(self):
        user_no_baseline = uuid4()
        state = self.use_case.execute(
            GetHomeStateCommand(user_id=user_no_baseline, today=date.today())
        )
        assert state.current_cycle_day is None
        assert state.current_phase is None

    def test_logs_until_unlock_decrements(self):
        for i in range(10):
            self.log_repo.save(
                make_log_directly(self.user_id, date.today() - timedelta(days=i))
            )
        state = self.use_case.execute(
            GetHomeStateCommand(user_id=self.user_id, today=date.today())
        )
        assert state.logs_until_unlock == INSIGHT_UNLOCK_THRESHOLD - 10

    def test_early_feedback_shown_when_available(self):
        from domain.models.pattern import EarlyFeedback
        feedback = EarlyFeedback(
            user_id=self.user_id,
            message="You tend to log higher pain during your luteal phase.",
            generated_at=datetime.utcnow(),
            log_count=10,
        )
        self.pattern_repo.save_feedback(feedback)
        state = self.use_case.execute(
            GetHomeStateCommand(user_id=self.user_id, today=date.today())
        )
        assert state.early_feedback is not None
        assert "luteal" in state.early_feedback


# ---------------------------------------------------------------------------
# GenerateEarlyFeedback
# ---------------------------------------------------------------------------

class TestGenerateEarlyFeedback:

    def setup_method(self):
        self.log_repo = InMemoryLogRepository()
        self.pattern_repo = InMemoryPatternRepository()
        self.publisher = InMemoryEventPublisher()
        self.use_case = GenerateEarlyFeedback(
            self.log_repo, self.pattern_repo, self.publisher
        )
        self.user_id = uuid4()

    def _seed_logs(self, count: int):
        for i in range(count):
            phase = CyclePhase.LUTEAL if (i % 28) >= 14 else CyclePhase.FOLLICULAR
            pain = 7 if (i % 28) >= 14 else 2
            log = make_log_directly(
                self.user_id,
                date.today() - timedelta(days=count - i),
                cycle_day=(i % 28) + 1,
                phase=phase,
                pain=pain,
            )
            self.log_repo.save(log)

    def test_returns_not_generated_with_few_logs(self):
        self._seed_logs(3)
        result = self.use_case.execute(
            GenerateEarlyFeedbackCommand(user_id=self.user_id)
        )
        assert result.was_generated is False

    def test_generates_feedback_with_enough_logs(self):
        self._seed_logs(14)
        result = self.use_case.execute(
            GenerateEarlyFeedbackCommand(user_id=self.user_id)
        )
        assert result.was_generated is True
        assert result.feedback is not None

    def test_saves_feedback_to_repository(self):
        self._seed_logs(14)
        self.use_case.execute(
            GenerateEarlyFeedbackCommand(user_id=self.user_id)
        )
        assert self.pattern_repo.get_latest_feedback(self.user_id) is not None

    def test_publishes_feedback_generated_event(self):
        self._seed_logs(14)
        self.use_case.execute(
            GenerateEarlyFeedbackCommand(user_id=self.user_id)
        )
        assert len(self.publisher.of_type(EarlyFeedbackGenerated)) == 1
