"""
Cycle

Three things live here:

1. Score — a validated 0–10 integer used for pain, energy, and mood.
   It is a value object: immutable, self-validating, comparable.

2. CyclePhase — the four standard menstrual cycle phases plus UNKNOWN
   for users who report irregular cycles or where inference is not yet
   possible. UNKNOWN is a first-class value, not an error state.

3. CycleBaseline — the cycle information collected at onboarding.
   This is the anchor the PhaseCalculator uses to infer cycle phase
   for each daily log. It is mutable over time as the user updates
   their cycle info in settings.

Design notes:
- average_cycle_length is Optional[int]. None means the user reported
  irregular cycles or chose "not sure". The engine must handle this
  gracefully — irregular does not mean no data, it means wider windows.
- CycleBaseline is NOT a log. It is configuration. Do not store it
  alongside DailyLog records.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Optional
from uuid import UUID


# ---------------------------------------------------------------------------
# Score — value object
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Score:
    """
    A validated integer score on a 0–10 scale.

    Used for pain_level, energy_level, and mood_level.
    Frozen so it cannot be mutated after creation.

    Usage:
        pain = Score(7)
        energy = Score(0)
        Score(11)  # raises ValueError
    """

    value: int

    def __post_init__(self) -> None:
        if not isinstance(self.value, int):
            raise TypeError(f"Score value must be an int, got {type(self.value).__name__}")
        if not (0 <= self.value <= 10):
            raise ValueError(f"Score must be between 0 and 10 inclusive, got {self.value}")

    def __int__(self) -> int:
        return self.value

    def __float__(self) -> float:
        return float(self.value)

    def __le__(self, other: Score) -> bool:
        return self.value <= other.value

    def __lt__(self, other: Score) -> bool:
        return self.value < other.value

    def __ge__(self, other: Score) -> bool:
        return self.value >= other.value

    def __gt__(self, other: Score) -> bool:
        return self.value > other.value

    def is_high(self, threshold: int = 7) -> bool:
        """Convenience: is this score at or above a given threshold?"""
        return self.value >= threshold

    def is_low(self, threshold: int = 3) -> bool:
        """Convenience: is this score at or below a given threshold?"""
        return self.value <= threshold

    @classmethod
    def zero(cls) -> Score:
        return cls(0)

    @classmethod
    def max(cls) -> Score:
        return cls(10)


# ---------------------------------------------------------------------------
# CyclePhase — enum
# ---------------------------------------------------------------------------

class CyclePhase(str, Enum):
    """
    The four standard menstrual cycle phases.

    UNKNOWN is a valid phase, not an error. It is used when:
    - The user reported an irregular cycle at onboarding
    - Insufficient data exists to infer the phase
    - The cycle baseline has not yet been set

    Phase day ranges (approximate, for a 28-day cycle):
        MENSTRUAL:   days 1–5
        FOLLICULAR:  days 6–13
        OVULATORY:   days 14–16
        LUTEAL:      days 17–28

    These ranges are adjusted proportionally for cycle lengths other than 28.
    The PhaseCalculator handles this logic; the enum itself carries no math.
    """

    MENSTRUAL = "menstrual"
    FOLLICULAR = "follicular"
    OVULATORY = "ovulatory"
    LUTEAL = "luteal"
    UNKNOWN = "unknown"

    @property
    def is_known(self) -> bool:
        return self != CyclePhase.UNKNOWN

    @property
    def display_name(self) -> str:
        return self.value.capitalize()


# ---------------------------------------------------------------------------
# CycleBaseline — dataclass
# ---------------------------------------------------------------------------

@dataclass
class CycleBaseline:
    """
    The cycle configuration for a single user.

    Collected at onboarding and editable from Settings.
    Used by PhaseCalculator to infer cycle day and phase for each DailyLog.

    Fields:
        user_id:               The user this baseline belongs to.
        last_period_start:     The date the user's most recent period began.
                               This is the anchor for all phase calculations.
        average_cycle_length:  Typical cycle length in days. None if the user
                               reported irregular cycles or chose "not sure".
                               Default 28 is NOT assumed — None is preserved.
        is_irregular:          True if the user explicitly reported an irregular
                               cycle. Affects how the engine widens phase windows.
        updated_at:            When this baseline was last modified. Tracked so
                               the audit log can record changes over time.

    Invariants:
        - last_period_start cannot be in the future.
        - average_cycle_length, if set, must be between 21 and 45 days.
          Outside this range is clinically atypical and likely a data entry error.
        - is_irregular and a non-None average_cycle_length can coexist:
          a user may know their approximate length but still consider
          themselves irregular.
    """

    user_id: UUID
    last_period_start: date
    average_cycle_length: Optional[int]
    is_irregular: bool
    updated_at: datetime

    # Typical clinical bounds for cycle length
    MIN_CYCLE_LENGTH: int = field(default=21, init=False, repr=False)
    MAX_CYCLE_LENGTH: int = field(default=45, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.last_period_start > date.today():
            raise ValueError("last_period_start cannot be in the future")

        if self.average_cycle_length is not None:
            if not (self.MIN_CYCLE_LENGTH <= self.average_cycle_length <= self.MAX_CYCLE_LENGTH):
                raise ValueError(
                    f"average_cycle_length must be between "
                    f"{self.MIN_CYCLE_LENGTH} and {self.MAX_CYCLE_LENGTH}, "
                    f"got {self.average_cycle_length}"
                )

    @property
    def effective_cycle_length(self) -> int:
        """
        The cycle length to use in phase calculations.

        Returns the user-provided length if available, otherwise falls back
        to 28 as a clinical default. Callers should treat results for
        irregular users with wider confidence intervals.
        """
        return self.average_cycle_length if self.average_cycle_length is not None else 28

    @property
    def has_reliable_baseline(self) -> bool:
        """
        True if we have enough information for confident phase inference.
        False for irregular users with no provided cycle length.
        """
        return not self.is_irregular or self.average_cycle_length is not None
