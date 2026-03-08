"""
Tests for domain.models.cycle

Covers:
- Score: construction, validation, comparison, convenience methods
- CyclePhase: enum values, properties
- CycleBaseline: validation, derived properties
"""

import pytest
from datetime import date, datetime, timedelta
from uuid import uuid4

from domain.models.cycle import Score, CyclePhase, CycleBaseline


# ---------------------------------------------------------------------------
# Score
# ---------------------------------------------------------------------------

class TestScore:

    def test_valid_score_construction(self):
        for value in range(0, 11):
            s = Score(value)
            assert s.value == value

    def test_score_below_zero_raises(self):
        with pytest.raises(ValueError, match="between 0 and 10"):
            Score(-1)

    def test_score_above_ten_raises(self):
        with pytest.raises(ValueError, match="between 0 and 10"):
            Score(11)

    def test_score_requires_int(self):
        with pytest.raises(TypeError, match="must be an int"):
            Score(7.5)  # type: ignore

    def test_score_is_frozen(self):
        s = Score(5)
        with pytest.raises(Exception):
            s.value = 6  # type: ignore

    def test_score_zero_classmethod(self):
        assert Score.zero().value == 0

    def test_score_max_classmethod(self):
        assert Score.max().value == 10

    def test_int_conversion(self):
        assert int(Score(7)) == 7

    def test_float_conversion(self):
        assert float(Score(7)) == 7.0

    def test_comparison_operators(self):
        low = Score(2)
        high = Score(8)
        assert low < high
        assert high > low
        assert low <= Score(2)
        assert high >= Score(8)

    def test_is_high_default_threshold(self):
        assert Score(7).is_high() is True
        assert Score(6).is_high() is False

    def test_is_high_custom_threshold(self):
        assert Score(5).is_high(threshold=5) is True
        assert Score(4).is_high(threshold=5) is False

    def test_is_low_default_threshold(self):
        assert Score(3).is_low() is True
        assert Score(4).is_low() is False

    def test_is_low_custom_threshold(self):
        assert Score(2).is_low(threshold=2) is True
        assert Score(3).is_low(threshold=2) is False

    def test_equality(self):
        assert Score(5) == Score(5)
        assert Score(5) != Score(6)

    def test_boundary_values(self):
        # 0 and 10 are valid
        assert Score(0).value == 0
        assert Score(10).value == 10


# ---------------------------------------------------------------------------
# CyclePhase
# ---------------------------------------------------------------------------

class TestCyclePhase:

    def test_all_phases_exist(self):
        phases = {p.value for p in CyclePhase}
        assert "menstrual" in phases
        assert "follicular" in phases
        assert "ovulatory" in phases
        assert "luteal" in phases
        assert "unknown" in phases

    def test_is_known_for_known_phases(self):
        for phase in [CyclePhase.MENSTRUAL, CyclePhase.FOLLICULAR,
                      CyclePhase.OVULATORY, CyclePhase.LUTEAL]:
            assert phase.is_known is True

    def test_is_known_false_for_unknown(self):
        assert CyclePhase.UNKNOWN.is_known is False

    def test_display_name_capitalised(self):
        assert CyclePhase.LUTEAL.display_name == "Luteal"
        assert CyclePhase.UNKNOWN.display_name == "Unknown"

    def test_phase_is_string_enum(self):
        # Ensures it serialises cleanly to string (important for JSON/DB)
        assert CyclePhase.MENSTRUAL == "menstrual"


# ---------------------------------------------------------------------------
# CycleBaseline
# ---------------------------------------------------------------------------

class TestCycleBaseline:

    def _valid_baseline(self, **overrides) -> CycleBaseline:
        defaults = dict(
            user_id=uuid4(),
            last_period_start=date.today() - timedelta(days=10),
            average_cycle_length=28,
            is_irregular=False,
            updated_at=datetime.utcnow(),
        )
        defaults.update(overrides)
        return CycleBaseline(**defaults)

    def test_valid_baseline_construction(self):
        baseline = self._valid_baseline()
        assert baseline.average_cycle_length == 28

    def test_future_period_start_raises(self):
        with pytest.raises(ValueError, match="cannot be in the future"):
            self._valid_baseline(last_period_start=date.today() + timedelta(days=1))

    def test_cycle_length_below_minimum_raises(self):
        with pytest.raises(ValueError, match="between"):
            self._valid_baseline(average_cycle_length=20)

    def test_cycle_length_above_maximum_raises(self):
        with pytest.raises(ValueError, match="between"):
            self._valid_baseline(average_cycle_length=46)

    def test_minimum_valid_cycle_length(self):
        baseline = self._valid_baseline(average_cycle_length=21)
        assert baseline.average_cycle_length == 21

    def test_maximum_valid_cycle_length(self):
        baseline = self._valid_baseline(average_cycle_length=45)
        assert baseline.average_cycle_length == 45

    def test_none_cycle_length_is_valid(self):
        # Irregular users may not provide a length
        baseline = self._valid_baseline(average_cycle_length=None, is_irregular=True)
        assert baseline.average_cycle_length is None

    def test_effective_cycle_length_returns_provided_value(self):
        baseline = self._valid_baseline(average_cycle_length=32)
        assert baseline.effective_cycle_length == 32

    def test_effective_cycle_length_defaults_to_28_when_none(self):
        baseline = self._valid_baseline(average_cycle_length=None, is_irregular=True)
        assert baseline.effective_cycle_length == 28

    def test_has_reliable_baseline_regular_user(self):
        baseline = self._valid_baseline(is_irregular=False, average_cycle_length=28)
        assert baseline.has_reliable_baseline is True

    def test_has_reliable_baseline_irregular_with_length(self):
        # Irregular but has provided a length — still usable
        baseline = self._valid_baseline(is_irregular=True, average_cycle_length=35)
        assert baseline.has_reliable_baseline is True

    def test_has_reliable_baseline_irregular_without_length(self):
        # Irregular and no length — least confident case
        baseline = self._valid_baseline(is_irregular=True, average_cycle_length=None)
        assert baseline.has_reliable_baseline is False

    def test_irregular_and_cycle_length_can_coexist(self):
        # A user can report irregular cycles but still know their approximate length
        baseline = self._valid_baseline(is_irregular=True, average_cycle_length=30)
        assert baseline.is_irregular is True
        assert baseline.average_cycle_length == 30

    def test_today_as_period_start_is_valid(self):
        # Today is not in the future
        baseline = self._valid_baseline(last_period_start=date.today())
        assert baseline.last_period_start == date.today()
