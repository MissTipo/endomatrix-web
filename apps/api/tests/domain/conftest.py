"""
conftest.py

Shared fixtures for the EndoMatrix test suite.

Fixtures defined here are available to all tests without explicit import.
Keep this file lean — only fixtures that are genuinely shared across
multiple test modules belong here. Module-specific fixtures stay in
their own test file.
"""

import pytest
from datetime import date, datetime, timedelta
from uuid import uuid4

from domain.models.cycle import CycleBaseline, CyclePhase, Score
from domain.models.daily_log import DailyLog
from domain.models.symptom import Symptom


@pytest.fixture
def user_id():
    """A stable UUID representing a test user."""
    return uuid4()


@pytest.fixture
def today():
    return date.today()


@pytest.fixture
def now():
    return datetime.utcnow()


@pytest.fixture
def regular_cycle_baseline(user_id, now):
    """A standard 28-day cycle baseline for a regular user."""
    return CycleBaseline(
        user_id=user_id,
        last_period_start=date.today() - timedelta(days=10),
        average_cycle_length=28,
        is_irregular=False,
        updated_at=now,
    )


@pytest.fixture
def irregular_cycle_baseline(user_id, now):
    """A baseline for a user with irregular cycles and no known length."""
    return CycleBaseline(
        user_id=user_id,
        last_period_start=date.today() - timedelta(days=14),
        average_cycle_length=None,
        is_irregular=True,
        updated_at=now,
    )


@pytest.fixture
def high_pain_log(user_id, now):
    """A daily log with high pain and low energy — a symptomatic day."""
    return DailyLog(
        id=uuid4(),
        user_id=user_id,
        logged_date=date.today(),
        pain_level=Score(8),
        energy_level=Score(2),
        dominant_symptom=Symptom.PELVIC_PAIN,
        cycle_day=22,
        cycle_phase=CyclePhase.LUTEAL,
        created_at=now,
    )


@pytest.fixture
def low_pain_log(user_id, now):
    """A daily log with low pain and good energy — a non-symptomatic day."""
    return DailyLog(
        id=uuid4(),
        user_id=user_id,
        logged_date=date.today() - timedelta(days=1),
        pain_level=Score(1),
        energy_level=Score(8),
        dominant_symptom=Symptom.BLOATING,
        cycle_day=10,
        cycle_phase=CyclePhase.FOLLICULAR,
        created_at=now,
    )


@pytest.fixture
def thirty_days_of_logs(user_id, now):
    """
    30 consecutive daily logs for a single user.
    Pain follows a luteal-phase spike pattern: rises from day 18 onward.
    Useful for testing pattern engine inputs.
    """
    logs = []
    for i in range(30):
        log_date = date.today() - timedelta(days=29 - i)
        cycle_day = (i % 28) + 1

        # Simulate a luteal phase pain spike
        if cycle_day >= 18:
            pain = Score(min(10, 5 + (cycle_day - 18)))
            energy = Score(max(0, 6 - (cycle_day - 18)))
            symptom = Symptom.PELVIC_PAIN
            phase = CyclePhase.LUTEAL
        else:
            pain = Score(2)
            energy = Score(7)
            symptom = Symptom.BLOATING
            phase = CyclePhase.FOLLICULAR

        logs.append(DailyLog(
            id=uuid4(),
            user_id=user_id,
            logged_date=log_date,
            pain_level=pain,
            energy_level=energy,
            dominant_symptom=symptom,
            cycle_day=cycle_day,
            cycle_phase=phase,
            created_at=now,
        ))
    return logs
