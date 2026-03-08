"""
DailyLog

The core unit of data in EndoMatrix. One per user per calendar day.

This is what the user produces in under 10 seconds on the Daily Log screen.
Everything the pattern engine reasons about derives from a sequence of these.

Design notes:
- logged_date is a date, not a datetime. One log per day is a hard invariant.
  The infrastructure layer enforces uniqueness on (user_id, logged_date).
- cycle_day and cycle_phase are SET BY THE SYSTEM at write time using
  CycleBaseline and PhaseCalculator. The user never provides these.
- mood_level and note are Optional — they are MVP additions. The v0 log
  has pain, energy, and dominant_symptom only. The domain models both
  v0 and MVP together because migrating this later is more expensive
  than carrying Optional fields now.
- created_at records when the log was written to the system, which may
  differ from logged_date if a user logs retroactively.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from .cycle import CyclePhase, Score
from .symptom import Symptom

# Maximum length for the optional free-text note.
# One sentence. Enforced here in the domain, not just the UI.
NOTE_MAX_LENGTH: int = 280


@dataclass(frozen=True)
class DailyLog:
    """
    A single day's symptom log for one user.

    Frozen: a submitted log is a record of what the user reported.
    It should not be mutated. If a user corrects an entry, the
    infrastructure layer creates a new log and marks the old one
    superseded — the domain model itself never changes.

    Fields:
        id:               Unique identifier for this log entry.
        user_id:          The user who submitted this log.
        logged_date:      The calendar date this log represents.
                          Not the submission time — one per day.
        pain_level:       Pain intensity, 0–10.
        energy_level:     Energy/fatigue level, 0–10. Higher = more energy.
        mood_level:       Mood level, 0–10. Optional (MVP). Higher = better mood.
        dominant_symptom: The single symptom that mattered most today.
        note:             Optional free-text note, max 280 characters.
                          One sentence. Not a journal.
        cycle_day:        Day in the current cycle, inferred by the system.
                          Day 1 = first day of menstruation.
        cycle_phase:      Inferred cycle phase at the time of logging.
        created_at:       When this record was created in the system.
    """

    id: UUID
    user_id: UUID
    logged_date: date
    pain_level: Score
    energy_level: Score
    dominant_symptom: Symptom
    cycle_day: int
    cycle_phase: CyclePhase
    created_at: datetime
    mood_level: Optional[Score] = None
    note: Optional[str] = None

    def __post_init__(self) -> None:
        if self.cycle_day < 1:
            raise ValueError(f"cycle_day must be >= 1, got {self.cycle_day}")

        if self.cycle_day > 60:
            # Cycles longer than 60 days are outside normal clinical range.
            # This is a data integrity guard, not a hard medical rule.
            raise ValueError(
                f"cycle_day {self.cycle_day} exceeds maximum expected value of 60. "
                "Check the CycleBaseline used for inference."
            )

        if self.note is not None:
            stripped = self.note.strip()
            if len(stripped) == 0:
                # Treat empty string as no note
                object.__setattr__(self, "note", None)
            elif len(stripped) > NOTE_MAX_LENGTH:
                raise ValueError(
                    f"note exceeds maximum length of {NOTE_MAX_LENGTH} characters "
                    f"(got {len(stripped)})"
                )

        if self.logged_date > date.today():
            raise ValueError(
                f"logged_date {self.logged_date} is in the future. "
                "Logs cannot be submitted for future dates."
            )

    @property
    def is_high_pain_day(self) -> bool:
        """True if pain level is 7 or above."""
        return self.pain_level.is_high()

    @property
    def is_low_energy_day(self) -> bool:
        """True if energy level is 3 or below."""
        return self.energy_level.is_low()

    @property
    def is_symptomatic(self) -> bool:
        """
        True if this day shows meaningful symptom burden.
        Currently defined as high pain OR low energy. This definition
        may be refined as the pattern engine matures.
        """
        return self.is_high_pain_day or self.is_low_energy_day

    @property
    def has_mood(self) -> bool:
        """True if a mood score was recorded (MVP feature)."""
        return self.mood_level is not None

    @property
    def has_note(self) -> bool:
        """True if a free-text note was recorded."""
        return self.note is not None
