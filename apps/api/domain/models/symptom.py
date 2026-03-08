"""
Symptom

The controlled vocabulary for dominant symptoms a user can report.
This is a single-select per daily log — the symptom that mattered most that day.

Design notes:
- Keep this list stable. Adding values is fine; removing or renaming breaks
  historical data and any pattern analysis built on top of it.
- The ordering here is intentional: physical symptoms first, then systemic,
  then mood/cognitive. This mirrors the UI dropdown order.
"""

from enum import Enum


class Symptom(str, Enum):
    # Physical / localised
    PELVIC_PAIN = "pelvic_pain"
    LOWER_BACK_PAIN = "lower_back_pain"
    LEG_PAIN = "leg_pain"
    BLOATING = "bloating"
    NAUSEA = "nausea"
    HEADACHE = "headache"
    ACNE_FLARE = "acne_flare"

    # Systemic / mood / cognitive
    MOOD_CRASH = "mood_crash"
    BRAIN_FOG = "brain_fog"
    INSOMNIA = "insomnia"

    # Catch-all — always last
    OTHER = "other"

    def is_physical(self) -> bool:
        """Returns True for localised physical symptoms."""
        return self in {
            Symptom.PELVIC_PAIN,
            Symptom.LOWER_BACK_PAIN,
            Symptom.LEG_PAIN,
            Symptom.BLOATING,
            Symptom.NAUSEA,
            Symptom.HEADACHE,
            Symptom.ACNE_FLARE,
        }

    def is_systemic(self) -> bool:
        """Returns True for mood, cognitive, and sleep symptoms."""
        return self in {
            Symptom.MOOD_CRASH,
            Symptom.BRAIN_FOG,
            Symptom.INSOMNIA,
        }
