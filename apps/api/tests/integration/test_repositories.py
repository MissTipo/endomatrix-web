"""
tests/integration/test_repositories.py

Integration tests for PostgresLogRepository, PostgresCycleRepository,
PostgresPatternRepository, and DatabaseEventPublisher.

These tests run the same contract as tests/ports/test_ports_contract.py
but against a real PostgreSQL database. If the contract tests pass against
fakes AND these pass against Postgres, the implementations are correct.

Run with:
    TEST_DATABASE_URL=postgresql+psycopg2://... pytest tests/integration/ -v

Skipped automatically if TEST_DATABASE_URL is not set.
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
    SymptomCluster,
    PhasePattern,
)
from domain.models.symptom import Symptom
from infrastructure.repositories.cycle_repository import PostgresCycleRepository
from infrastructure.repositories.log_repository import PostgresLogRepository
from infrastructure.repositories.pattern_repository import PostgresPatternRepository
from infrastructure.events.publisher import DatabaseEventPublisher


# ---------------------------------------------------------------------------
# Helpers (same as contract tests to keep tests readable)
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
        cycles_analyzed=2,
        total_logs=30,
        symptom_onset_range=(18, 24),
        escalation_speed=EscalationSpeed.MODERATE,
        symptom_clusters=[
            SymptomCluster(
                symptoms=frozenset({Symptom.PELVIC_PAIN, Symptom.BLOATING}),
                typical_phase=CyclePhase.LUTEAL,
                occurrence_rate=0.65,
            )
        ],
        phase_patterns=[
            PhasePattern(
                phase=CyclePhase.LUTEAL,
                onset_day_range=(18, 24),
                average_pain=6.5,
                average_energy=4.2,
                dominant_symptoms=[Symptom.PELVIC_PAIN, Symptom.BLOATING],
                severity_trend=SeverityTrend.STABLE,
                log_count=12,
            )
        ],
        severity_trend=SeverityTrend.STABLE,
    )


# ---------------------------------------------------------------------------
# PostgresLogRepository
# ---------------------------------------------------------------------------

class TestPostgresLogRepository:

    @pytest.fixture(autouse=True)
    def setup(self, db_session):
        self.repo = PostgresLogRepository(db_session)
        self.user_id = uuid4()

    def test_save_and_retrieve_by_id(self):
        log = make_log(self.user_id, date.today())
        self.repo.save(log)
        retrieved = self.repo.get_by_id(log.id)
        assert retrieved is not None
        assert retrieved.id == log.id
        assert retrieved.pain_level == log.pain_level

    def test_get_by_date_returns_active_log(self):
        log = make_log(self.user_id, date.today())
        self.repo.save(log)
        result = self.repo.get_by_date(self.user_id, date.today())
        assert result is not None
        assert result.id == log.id

    def test_supersession_marks_old_log_inactive(self):
        original = make_log(self.user_id, date.today())
        self.repo.save(original)
        replacement = make_log(self.user_id, date.today())
        self.repo.save(replacement)

        # Old log is no longer retrievable by ID
        assert self.repo.get_by_id(original.id) is None
        # New log is returned by date
        active = self.repo.get_by_date(self.user_id, date.today())
        assert active is not None
        assert active.id == replacement.id

    def test_count_excludes_superseded(self):
        log = make_log(self.user_id, date.today())
        self.repo.save(log)
        replacement = make_log(self.user_id, date.today())
        self.repo.save(replacement)
        assert self.repo.count_logs_for_user(self.user_id) == 1

    def test_get_logs_for_user_ordered_descending(self):
        for i in range(3):
            self.repo.save(make_log(self.user_id, date.today() - timedelta(days=i)))
        logs = self.repo.get_logs_for_user(self.user_id)
        dates = [l.logged_date for l in logs]
        assert dates == sorted(dates, reverse=True)

    def test_get_logs_for_user_respects_limit_and_offset(self):
        for i in range(5):
            self.repo.save(make_log(self.user_id, date.today() - timedelta(days=i)))
        page = self.repo.get_logs_for_user(self.user_id, limit=2, offset=1)
        assert len(page) == 2

    def test_get_logs_in_range(self):
        for i in range(7):
            self.repo.save(make_log(self.user_id, date.today() - timedelta(days=i)))
        start = date.today() - timedelta(days=4)
        end = date.today() - timedelta(days=1)
        logs = self.repo.get_logs_in_range(self.user_id, start, end)
        assert len(logs) == 4
        assert all(start <= l.logged_date <= end for l in logs)

    def test_has_log_for_date(self):
        assert not self.repo.has_log_for_date(self.user_id, date.today())
        self.repo.save(make_log(self.user_id, date.today()))
        assert self.repo.has_log_for_date(self.user_id, date.today())

    def test_mood_and_note_round_trip(self):
        log = DailyLog(
            id=uuid4(),
            user_id=self.user_id,
            logged_date=date.today(),
            pain_level=Score(5),
            energy_level=Score(5),
            dominant_symptom=Symptom.BRAIN_FOG,
            cycle_day=14,
            cycle_phase=CyclePhase.FOLLICULAR,
            created_at=datetime.utcnow(),
            mood_level=Score(7),
            note="Rough afternoon.",
        )
        self.repo.save(log)
        retrieved = self.repo.get_by_date(self.user_id, date.today())
        assert retrieved is not None
        assert retrieved.mood_level == Score(7)
        assert retrieved.note == "Rough afternoon."


# ---------------------------------------------------------------------------
# PostgresCycleRepository
# ---------------------------------------------------------------------------

class TestPostgresCycleRepository:

    @pytest.fixture(autouse=True)
    def setup(self, db_session):
        self.repo = PostgresCycleRepository(db_session)
        self.user_id = uuid4()

    def test_save_and_retrieve(self):
        baseline = make_baseline(self.user_id)
        self.repo.save(baseline)
        result = self.repo.get_by_user_id(self.user_id)
        assert result is not None
        assert result.user_id == self.user_id
        assert result.average_cycle_length == 28

    def test_upsert_replaces_existing(self):
        self.repo.save(make_baseline(self.user_id))
        updated = CycleBaseline(
            user_id=self.user_id,
            last_period_start=date.today() - timedelta(days=3),
            average_cycle_length=30,
            is_irregular=False,
            updated_at=datetime.utcnow(),
        )
        self.repo.save(updated)
        result = self.repo.get_by_user_id(self.user_id)
        assert result is not None
        assert result.average_cycle_length == 30

    def test_exists_true_after_save(self):
        self.repo.save(make_baseline(self.user_id))
        assert self.repo.exists(self.user_id) is True

    def test_exists_false_when_missing(self):
        assert self.repo.exists(uuid4()) is False

    def test_irregular_baseline_none_cycle_length(self):
        baseline = CycleBaseline(
            user_id=self.user_id,
            last_period_start=date.today() - timedelta(days=5),
            average_cycle_length=None,
            is_irregular=True,
            updated_at=datetime.utcnow(),
        )
        self.repo.save(baseline)
        result = self.repo.get_by_user_id(self.user_id)
        assert result is not None
        assert result.average_cycle_length is None
        assert result.is_irregular is True


# ---------------------------------------------------------------------------
# PostgresPatternRepository
# ---------------------------------------------------------------------------

class TestPostgresPatternRepository:

    @pytest.fixture(autouse=True)
    def setup(self, db_session):
        self.repo = PostgresPatternRepository(db_session)
        self.user_id = uuid4()

    def test_save_and_retrieve_latest(self):
        pattern = make_pattern(self.user_id)
        self.repo.save_pattern(pattern)
        result = self.repo.get_latest_pattern(self.user_id)
        assert result is not None
        assert result.id == pattern.id

    def test_nested_types_round_trip(self):
        pattern = make_pattern(self.user_id)
        self.repo.save_pattern(pattern)
        result = self.repo.get_latest_pattern(self.user_id)
        assert result is not None
        assert len(result.symptom_clusters) == 1
        assert len(result.phase_patterns) == 1
        cluster = result.symptom_clusters[0]
        assert Symptom.PELVIC_PAIN in cluster.symptoms
        assert cluster.typical_phase == CyclePhase.LUTEAL

    def test_get_latest_returns_most_recent(self):
        older = PatternResult(
            id=uuid4(),
            user_id=self.user_id,
            generated_at=datetime.utcnow() - timedelta(days=30),
            cycles_analyzed=1,
            total_logs=14,
            symptom_onset_range=(18, 24),
            escalation_speed=EscalationSpeed.GRADUAL,
            symptom_clusters=[],
            phase_patterns=[],
            severity_trend=SeverityTrend.STABLE,
        )
        newer = make_pattern(self.user_id)
        self.repo.save_pattern(older)
        self.repo.save_pattern(newer)
        result = self.repo.get_latest_pattern(self.user_id)
        assert result is not None
        assert result.id == newer.id

    def test_get_pattern_by_id(self):
        pattern = make_pattern(self.user_id)
        self.repo.save_pattern(pattern)
        result = self.repo.get_pattern_by_id(pattern.id)
        assert result is not None
        assert result.id == pattern.id

    def test_get_pattern_by_id_returns_none_when_missing(self):
        assert self.repo.get_pattern_by_id(uuid4()) is None

    def test_count_patterns(self):
        for _ in range(3):
            self.repo.save_pattern(make_pattern(self.user_id))
        assert self.repo.count_patterns(self.user_id) == 3

    def test_save_and_retrieve_feedback(self):
        fb = EarlyFeedback(
            user_id=self.user_id,
            message="You tend to log higher pain in your luteal phase.",
            generated_at=datetime.utcnow(),
            log_count=10,
            trigger_phase=CyclePhase.LUTEAL,
        )
        self.repo.save_feedback(fb)
        result = self.repo.get_latest_feedback(self.user_id)
        assert result is not None
        assert result.message == fb.message
        assert result.trigger_phase == CyclePhase.LUTEAL


# ---------------------------------------------------------------------------
# DatabaseEventPublisher
# ---------------------------------------------------------------------------

class TestDatabaseEventPublisher:

    @pytest.fixture(autouse=True)
    def setup(self, db_session):
        self.publisher = DatabaseEventPublisher(db_session)
        self.session = db_session
        self.user_id = uuid4()

    def _count_events(self) -> int:
        from sqlalchemy import text
        result = self.session.execute(
            text("SELECT COUNT(*) FROM audit_events WHERE user_id = :uid"),
            {"uid": str(self.user_id)},
        )
        return result.scalar()

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
        assert self._count_events() == 1

    def test_publish_all_writes_all_events(self):
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
        assert self._count_events() == 3

    def test_event_type_is_class_name(self):
        from sqlalchemy import text
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
        row = self.session.execute(
            text("SELECT event_type FROM audit_events WHERE user_id = :uid LIMIT 1"),
            {"uid": str(self.user_id)},
        ).one()
        assert row[0] == "LogCreated"
