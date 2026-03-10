"""
PhaseCalculator

Infers cycle day and cycle phase from a CycleBaseline and a target date.

This is pure computation. No I/O, no side effects, no dependencies
outside the domain models. It takes data in and returns data out.

Phase boundaries for a standard 28-day cycle:
    Menstrual:   days  1 –  5   (bleeding)
    Follicular:  days  6 – 11   (follicle development)
    Ovulatory:   days 12 – 14   (ovulation window)
    Luteal:      days 15 – 28   (post-ovulation, most symptomatic)

For cycles other than 28 days, the luteal phase is the most
biologically consistent anchor — it is approximately 14 days long
ending at menstruation for most people. We use it as a fixed
reference point and scale the follicular phase to absorb the
variation.

Scaling logic for a cycle of length L:
    Menstrual:   days 1 – 5                          (fixed)
    Luteal:      days (L - 13) – L                   (fixed ~14 days)
    Ovulatory:   days (L - 16) – (L - 14)            (fixed 3 days)
    Follicular:  days 6 – (L - 17)                   (absorbs variation)

For short cycles (21 days), follicular may be very short or absent.
For long cycles (35+ days), follicular is extended.
The calculator handles edge cases gracefully and falls back to
CyclePhase.UNKNOWN rather than producing wrong answers.

Design note on irregular cycles:
    When is_irregular is True and no average_cycle_length is provided,
    CycleBaseline.effective_cycle_length returns 28 as a default.
    The calculator uses this but marks results as lower confidence.
    It is the responsibility of callers to check
    CycleBaseline.has_reliable_baseline before presenting results
    to users as definitive.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from domain.models.cycle import CycleBaseline, CyclePhase


# Minimum number of days the follicular phase must span.
# If scaling produces a follicular phase shorter than this,
# we skip it and move directly from menstrual to ovulatory.
MIN_FOLLICULAR_DAYS = 1

# Menstrual phase is biologically fixed regardless of cycle length.
MENSTRUAL_END_DAY = 5

# Luteal phase is approximately 14 days, anchored to the end of the cycle.
LUTEAL_DURATION = 14

# Ovulatory window is approximately 3 days, immediately before luteal.
OVULATORY_DURATION = 3


@dataclass(frozen=True)
class PhaseResult:
    """
    The output of a single phase calculation.

    cycle_day:        Day number within the current cycle (1-indexed).
                      Day 1 = first day of the most recent period.
    phase:            The inferred cycle phase for this day.
    is_reliable:      False if the baseline is irregular with no
                      provided cycle length. Callers should qualify
                      how they present this result to users.
    days_until_next:  Estimated days until the next period starts.
                      None if cycle_day exceeds expected cycle length
                      (which can happen with irregular cycles).
    """

    cycle_day: int
    phase: CyclePhase
    is_reliable: bool
    days_until_next: int | None


class PhaseCalculator:
    """
    Computes cycle day and phase from a baseline and a target date.

    Stateless. Create once and call as many times as needed.

    Usage:
        calculator = PhaseCalculator()
        result = calculator.calculate(baseline, target_date)
        print(result.cycle_day)   # e.g. 22
        print(result.phase)       # CyclePhase.LUTEAL
    """

    def calculate(self, baseline: CycleBaseline, target_date: date) -> PhaseResult:
        """
        Calculate the cycle day and phase for target_date given baseline.

        If target_date is before last_period_start, returns day 1 in
        CyclePhase.UNKNOWN — we cannot infer a phase before the anchor.
        """
        delta = (target_date - baseline.last_period_start).days

        if delta < 0:
            # Date is before the known period start — cannot infer
            return PhaseResult(
                cycle_day=1,
                phase=CyclePhase.UNKNOWN,
                is_reliable=False,
                days_until_next=None,
            )

        cycle_length = baseline.effective_cycle_length

        # Cycle day is 1-indexed: day 0 delta = day 1
        cycle_day = (delta % cycle_length) + 1

        phase = self._infer_phase(cycle_day, cycle_length)

        days_until_next = cycle_length - cycle_day

        return PhaseResult(
            cycle_day=cycle_day,
            phase=phase,
            is_reliable=baseline.has_reliable_baseline,
            days_until_next=days_until_next,
        )

    def _infer_phase(self, cycle_day: int, cycle_length: int) -> CyclePhase:
        """
        Map a cycle day to a phase given the cycle length.

        Returns CyclePhase.UNKNOWN if the cycle length is too short
        to produce a meaningful phase boundary calculation.
        """
        if cycle_length < 21:
            # Outside the clinically expected range — do not guess
            return CyclePhase.UNKNOWN

        luteal_start = cycle_length - LUTEAL_DURATION + 1
        ovulatory_start = luteal_start - OVULATORY_DURATION
        follicular_start = MENSTRUAL_END_DAY + 1

        if cycle_day <= MENSTRUAL_END_DAY:
            return CyclePhase.MENSTRUAL

        if ovulatory_start > follicular_start and cycle_day < ovulatory_start:
            return CyclePhase.FOLLICULAR

        if cycle_day < luteal_start:
            return CyclePhase.OVULATORY

        return CyclePhase.LUTEAL

    def bulk_calculate(
        self,
        baseline: CycleBaseline,
        dates: list[date],
    ) -> dict[date, PhaseResult]:
        """
        Calculate phase results for multiple dates at once.

        Returns a dict mapping each date to its PhaseResult.
        Convenience helper for working with batches of dates.
        """
        return {d: self.calculate(baseline, d) for d in dates}

    def get_phase_boundaries(self, cycle_length: int) -> dict[CyclePhase, tuple[int, int]]:
        """
        Return the day boundaries for each phase for a given cycle length.

        Returns a dict mapping CyclePhase to (start_day, end_day) inclusive.
        Useful for the History calendar phase banding.

        Example for cycle_length=28:
            {
                CyclePhase.MENSTRUAL:  (1, 5),
                CyclePhase.FOLLICULAR: (6, 11),
                CyclePhase.OVULATORY:  (12, 14),
                CyclePhase.LUTEAL:     (15, 28),
            }
        """
        if cycle_length < 21:
            return {}

        luteal_start = cycle_length - LUTEAL_DURATION + 1
        ovulatory_start = max(luteal_start - OVULATORY_DURATION, MENSTRUAL_END_DAY + 1)
        follicular_start = MENSTRUAL_END_DAY + 1
        follicular_end = ovulatory_start - 1

        boundaries: dict[CyclePhase, tuple[int, int]] = {
            CyclePhase.MENSTRUAL: (1, MENSTRUAL_END_DAY),
            CyclePhase.LUTEAL: (luteal_start, cycle_length),
            CyclePhase.OVULATORY: (ovulatory_start, luteal_start - 1),
        }

        if follicular_end >= follicular_start:
            boundaries[CyclePhase.FOLLICULAR] = (follicular_start, follicular_end)

        return boundaries
