"""
Tests for domain.models.daily_log

Covers:
- Valid log construction for v0 (no mood, no note)
- Valid log construction for MVP (with mood and note)
- All validation rules on each field
- Derived properties: is_high_pain_day, is_low_energy_day, is_symptomatic
- Note edge cases: empty string, whitespace, max length
"""

import pytest
from datetime import date, datetime, timedelta
from uuid import uuid4

from domain.models.cycle import CyclePhase, Score
from domain.models.daily_log import DailyLog, NOTE_MAX_LENGTH
from domain.models.symptom import Symptom


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_log(**overrides) -> DailyLog:
    """Build a valid DailyLog with sensible defaults, applying any overrides."""
    defaults = dict(
        id=uuid4(),
        user_id=uuid4(),
        logged_date=date.today(),
        pain_level=Score(4),
        energy_level=Score(6),
        dominant_symptom=Symptom.PELVIC_PAIN,
        cycle_day=14,
        cycle_phase=CyclePhase.FOLLICULAR,
        created_at=datetime.utcnow(),
        mood_level=None,
        note=None,
    )
    defaults.update(overrides)
    return DailyLog(**defaults)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestDailyLogConstruction:

    def test_valid_v0_log(self):
        log = make_log()
        assert log.pain_level == Score(4)
        assert log.energy_level == Score(6)
        assert log.mood_level is None
        assert log.note is None

    def test_valid_mvp_log_with_mood_and_note(self):
        log = make_log(mood_level=Score(5), note="Feeling rough but manageable.")
        assert log.mood_level == Score(5)
        assert log.note == "Feeling rough but manageable."

    def test_log_is_frozen(self):
        log = make_log()
        with pytest.raises(Exception):
            log.pain_level = Score(9)  # type: ignore

    def test_future_logged_date_raises(self):
        with pytest.raises(ValueError, match="in the future"):
            make_log(logged_date=date.today() + timedelta(days=1))

    def test_today_is_valid_logged_date(self):
        log = make_log(logged_date=date.today())
        assert log.logged_date == date.today()

    def test_past_logged_date_is_valid(self):
        log = make_log(logged_date=date.today() - timedelta(days=30))
        assert log.logged_date is not None


# ---------------------------------------------------------------------------
# Cycle day validation
# ---------------------------------------------------------------------------

class TestDailyLogCycleDay:

    def test_cycle_day_one_is_valid(self):
        log = make_log(cycle_day=1)
        assert log.cycle_day == 1

    def test_cycle_day_zero_raises(self):
        with pytest.raises(ValueError, match=">= 1"):
            make_log(cycle_day=0)

    def test_cycle_day_negative_raises(self):
        with pytest.raises(ValueError, match=">= 1"):
            make_log(cycle_day=-5)

    def test_cycle_day_60_is_valid(self):
        log = make_log(cycle_day=60)
        assert log.cycle_day == 60

    def test_cycle_day_above_60_raises(self):
        with pytest.raises(ValueError, match="exceeds maximum"):
            make_log(cycle_day=61)


# ---------------------------------------------------------------------------
# Note validation
# ---------------------------------------------------------------------------

class TestDailyLogNote:

    def test_note_within_limit_is_valid(self):
        note = "a" * NOTE_MAX_LENGTH
        log = make_log(note=note)
        assert log.note == note

    def test_note_exceeding_limit_raises(self):
        note = "a" * (NOTE_MAX_LENGTH + 1)
        with pytest.raises(ValueError, match="exceeds maximum length"):
            make_log(note=note)

    def test_empty_note_becomes_none(self):
        log = make_log(note="")
        assert log.note is None

    def test_whitespace_only_note_becomes_none(self):
        log = make_log(note="   ")
        assert log.note is None

    def test_none_note_stays_none(self):
        log = make_log(note=None)
        assert log.note is None


# ---------------------------------------------------------------------------
# Derived properties
# ---------------------------------------------------------------------------

class TestDailyLogProperties:

    def test_is_high_pain_day_at_threshold(self):
        log = make_log(pain_level=Score(7))
        assert log.is_high_pain_day is True

    def test_is_high_pain_day_below_threshold(self):
        log = make_log(pain_level=Score(6))
        assert log.is_high_pain_day is False

    def test_is_low_energy_day_at_threshold(self):
        log = make_log(energy_level=Score(3))
        assert log.is_low_energy_day is True

    def test_is_low_energy_day_above_threshold(self):
        log = make_log(energy_level=Score(4))
        assert log.is_low_energy_day is False

    def test_is_symptomatic_high_pain(self):
        log = make_log(pain_level=Score(8), energy_level=Score(6))
        assert log.is_symptomatic is True

    def test_is_symptomatic_low_energy(self):
        log = make_log(pain_level=Score(2), energy_level=Score(2))
        assert log.is_symptomatic is True

    def test_is_symptomatic_both_high_pain_and_low_energy(self):
        log = make_log(pain_level=Score(8), energy_level=Score(1))
        assert log.is_symptomatic is True

    def test_not_symptomatic_moderate_values(self):
        log = make_log(pain_level=Score(4), energy_level=Score(6))
        assert log.is_symptomatic is False

    def test_has_mood_true_when_set(self):
        log = make_log(mood_level=Score(5))
        assert log.has_mood is True

    def test_has_mood_false_when_none(self):
        log = make_log(mood_level=None)
        assert log.has_mood is False

    def test_has_note_true_when_set(self):
        log = make_log(note="Some note.")
        assert log.has_note is True

    def test_has_note_false_when_none(self):
        log = make_log(note=None)
        assert log.has_note is False
