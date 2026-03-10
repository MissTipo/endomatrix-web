"""
Tests for domain.engine.phase_calculator

Covers:
- Standard 28-day cycle phase boundaries
- Variable cycle lengths (21, 35 days)
- Cycle day calculation across multiple cycles
- Irregular cycle handling
- Edge cases: date before period start, cycle day rollover
- Phase boundary helper
"""

import pytest
from datetime import date, datetime, timedelta
from uuid import uuid4

from domain.models.cycle import CycleBaseline, CyclePhase
from domain.engine.phase_calculator import PhaseCalculator, PhaseResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_baseline(
    last_period_start: date,
    cycle_length: int | None = 28,
    is_irregular: bool = False,
) -> CycleBaseline:
    return CycleBaseline(
        user_id=uuid4(),
        last_period_start=last_period_start,
        average_cycle_length=cycle_length,
        is_irregular=is_irregular,
        updated_at=datetime.utcnow(),
    )


@pytest.fixture
def calculator():
    return PhaseCalculator()


@pytest.fixture
def period_start():
    """A fixed period start date for deterministic tests."""
    return date(2025, 1, 1)


# ---------------------------------------------------------------------------
# Cycle day calculation
# ---------------------------------------------------------------------------

class TestCycleDayCalculation:

    def test_day_one_is_period_start(self, calculator, period_start):
        baseline = make_baseline(period_start)
        result = calculator.calculate(baseline, period_start)
        assert result.cycle_day == 1

    def test_day_five(self, calculator, period_start):
        baseline = make_baseline(period_start)
        result = calculator.calculate(baseline, period_start + timedelta(days=4))
        assert result.cycle_day == 5

    def test_day_28(self, calculator, period_start):
        baseline = make_baseline(period_start)
        result = calculator.calculate(baseline, period_start + timedelta(days=27))
        assert result.cycle_day == 28

    def test_cycle_resets_on_day_29(self, calculator, period_start):
        baseline = make_baseline(period_start)
        result = calculator.calculate(baseline, period_start + timedelta(days=28))
        assert result.cycle_day == 1

    def test_day_in_second_cycle(self, calculator, period_start):
        baseline = make_baseline(period_start)
        result = calculator.calculate(baseline, period_start + timedelta(days=35))
        assert result.cycle_day == 8

    def test_date_before_period_start_returns_unknown(self, calculator, period_start):
        baseline = make_baseline(period_start)
        result = calculator.calculate(baseline, period_start - timedelta(days=1))
        assert result.phase == CyclePhase.UNKNOWN
        assert result.is_reliable is False


# ---------------------------------------------------------------------------
# Phase boundaries — standard 28-day cycle
# ---------------------------------------------------------------------------

class TestPhaseFor28DayCycle:

    def test_day_1_is_menstrual(self, calculator, period_start):
        baseline = make_baseline(period_start, cycle_length=28)
        result = calculator.calculate(baseline, period_start)
        assert result.phase == CyclePhase.MENSTRUAL

    def test_day_5_is_menstrual(self, calculator, period_start):
        baseline = make_baseline(period_start, cycle_length=28)
        result = calculator.calculate(baseline, period_start + timedelta(days=4))
        assert result.phase == CyclePhase.MENSTRUAL

    def test_day_6_is_follicular(self, calculator, period_start):
        baseline = make_baseline(period_start, cycle_length=28)
        result = calculator.calculate(baseline, period_start + timedelta(days=5))
        assert result.phase == CyclePhase.FOLLICULAR

    def test_day_12_is_ovulatory(self, calculator, period_start):
        baseline = make_baseline(period_start, cycle_length=28)
        result = calculator.calculate(baseline, period_start + timedelta(days=11))
        assert result.phase == CyclePhase.OVULATORY

    def test_day_15_is_luteal(self, calculator, period_start):
        baseline = make_baseline(period_start, cycle_length=28)
        result = calculator.calculate(baseline, period_start + timedelta(days=14))
        assert result.phase == CyclePhase.LUTEAL

    def test_day_28_is_luteal(self, calculator, period_start):
        baseline = make_baseline(period_start, cycle_length=28)
        result = calculator.calculate(baseline, period_start + timedelta(days=27))
        assert result.phase == CyclePhase.LUTEAL


# ---------------------------------------------------------------------------
# Phase boundaries — 21-day cycle
# ---------------------------------------------------------------------------

class TestPhaseFor21DayCycle:

    def test_day_1_is_menstrual(self, calculator, period_start):
        baseline = make_baseline(period_start, cycle_length=21)
        result = calculator.calculate(baseline, period_start)
        assert result.phase == CyclePhase.MENSTRUAL

    def test_day_5_is_menstrual(self, calculator, period_start):
        baseline = make_baseline(period_start, cycle_length=21)
        result = calculator.calculate(baseline, period_start + timedelta(days=4))
        assert result.phase == CyclePhase.MENSTRUAL

    def test_luteal_starts_correctly(self, calculator, period_start):
        baseline = make_baseline(period_start, cycle_length=21)
        # luteal_start = 21 - 14 + 1 = 8
        result = calculator.calculate(baseline, period_start + timedelta(days=7))
        assert result.phase == CyclePhase.LUTEAL

    def test_day_21_is_luteal(self, calculator, period_start):
        baseline = make_baseline(period_start, cycle_length=21)
        result = calculator.calculate(baseline, period_start + timedelta(days=20))
        assert result.phase == CyclePhase.LUTEAL


# ---------------------------------------------------------------------------
# Phase boundaries — 35-day cycle
# ---------------------------------------------------------------------------

class TestPhaseFor35DayCycle:

    def test_day_1_is_menstrual(self, calculator, period_start):
        baseline = make_baseline(period_start, cycle_length=35)
        result = calculator.calculate(baseline, period_start)
        assert result.phase == CyclePhase.MENSTRUAL

    def test_day_6_is_follicular(self, calculator, period_start):
        baseline = make_baseline(period_start, cycle_length=35)
        result = calculator.calculate(baseline, period_start + timedelta(days=5))
        assert result.phase == CyclePhase.FOLLICULAR

    def test_luteal_starts_correctly(self, calculator, period_start):
        # luteal_start = 35 - 14 + 1 = 22
        baseline = make_baseline(period_start, cycle_length=35)
        result = calculator.calculate(baseline, period_start + timedelta(days=21))
        assert result.phase == CyclePhase.LUTEAL

    def test_day_35_is_luteal(self, calculator, period_start):
        baseline = make_baseline(period_start, cycle_length=35)
        result = calculator.calculate(baseline, period_start + timedelta(days=34))
        assert result.phase == CyclePhase.LUTEAL


# ---------------------------------------------------------------------------
# Reliability flag
# ---------------------------------------------------------------------------

class TestPhaseReliability:

    def test_regular_cycle_is_reliable(self, calculator, period_start):
        baseline = make_baseline(period_start, cycle_length=28, is_irregular=False)
        result = calculator.calculate(baseline, period_start + timedelta(days=10))
        assert result.is_reliable is True

    def test_irregular_with_no_length_is_unreliable(self, calculator, period_start):
        baseline = make_baseline(period_start, cycle_length=None, is_irregular=True)
        result = calculator.calculate(baseline, period_start + timedelta(days=10))
        assert result.is_reliable is False

    def test_irregular_with_length_is_reliable(self, calculator, period_start):
        baseline = make_baseline(period_start, cycle_length=32, is_irregular=True)
        result = calculator.calculate(baseline, period_start + timedelta(days=10))
        assert result.is_reliable is True


# ---------------------------------------------------------------------------
# Days until next period
# ---------------------------------------------------------------------------

class TestDaysUntilNext:

    def test_days_until_next_on_day_one(self, calculator, period_start):
        baseline = make_baseline(period_start, cycle_length=28)
        result = calculator.calculate(baseline, period_start)
        assert result.days_until_next == 27

    def test_days_until_next_on_last_day(self, calculator, period_start):
        baseline = make_baseline(period_start, cycle_length=28)
        result = calculator.calculate(baseline, period_start + timedelta(days=27))
        assert result.days_until_next == 0

    def test_days_until_next_returns_none_for_unknown(self, calculator, period_start):
        baseline = make_baseline(period_start)
        result = calculator.calculate(baseline, period_start - timedelta(days=1))
        assert result.days_until_next is None


# ---------------------------------------------------------------------------
# Bulk calculation
# ---------------------------------------------------------------------------

class TestBulkCalculate:

    def test_bulk_returns_result_for_every_date(self, calculator, period_start):
        baseline = make_baseline(period_start)
        dates = [period_start + timedelta(days=i) for i in range(28)]
        results = calculator.bulk_calculate(baseline, dates)
        assert len(results) == 28
        assert all(d in results for d in dates)

    def test_bulk_results_match_individual(self, calculator, period_start):
        baseline = make_baseline(period_start)
        target = period_start + timedelta(days=20)
        bulk = calculator.bulk_calculate(baseline, [target])
        individual = calculator.calculate(baseline, target)
        assert bulk[target] == individual


# ---------------------------------------------------------------------------
# Phase boundaries helper
# ---------------------------------------------------------------------------

class TestGetPhaseBoundaries:

    def test_28_day_boundaries(self, calculator):
        boundaries = calculator.get_phase_boundaries(28)
        assert CyclePhase.MENSTRUAL in boundaries
        assert CyclePhase.FOLLICULAR in boundaries
        assert CyclePhase.OVULATORY in boundaries
        assert CyclePhase.LUTEAL in boundaries

    def test_boundaries_are_contiguous(self, calculator):
        boundaries = calculator.get_phase_boundaries(28)
        # Collect all day numbers covered
        covered = set()
        for start, end in boundaries.values():
            for day in range(start, end + 1):
                covered.add(day)
        assert covered == set(range(1, 29))

    def test_boundaries_do_not_overlap(self, calculator):
        boundaries = calculator.get_phase_boundaries(28)
        all_days = []
        for start, end in boundaries.values():
            all_days.extend(range(start, end + 1))
        assert len(all_days) == len(set(all_days)), "Phase boundaries overlap"

    def test_short_cycle_returns_empty_for_invalid(self, calculator):
        boundaries = calculator.get_phase_boundaries(20)
        assert boundaries == {}

    def test_35_day_cycle_boundaries(self, calculator):
        boundaries = calculator.get_phase_boundaries(35)
        luteal_start, luteal_end = boundaries[CyclePhase.LUTEAL]
        assert luteal_end == 35
        assert (luteal_end - luteal_start + 1) == 14
