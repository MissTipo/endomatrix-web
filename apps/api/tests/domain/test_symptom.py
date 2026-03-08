"""
Tests for domain.models.symptom

Covers:
- Symptom enum values exist and are stable
- is_physical() and is_systemic() classify correctly
- Mutual exclusivity and coverage of classification methods
"""

import pytest
from domain.models.symptom import Symptom


class TestSymptom:

    def test_all_expected_symptoms_exist(self):
        expected = {
            "pelvic_pain", "lower_back_pain", "leg_pain", "bloating",
            "nausea", "headache", "acne_flare", "mood_crash",
            "brain_fog", "insomnia", "other",
        }
        actual = {s.value for s in Symptom}
        assert expected == actual

    def test_physical_symptoms(self):
        physical = [
            Symptom.PELVIC_PAIN,
            Symptom.LOWER_BACK_PAIN,
            Symptom.LEG_PAIN,
            Symptom.BLOATING,
            Symptom.NAUSEA,
            Symptom.HEADACHE,
            Symptom.ACNE_FLARE,
        ]
        for symptom in physical:
            assert symptom.is_physical() is True, f"{symptom} should be physical"
            assert symptom.is_systemic() is False, f"{symptom} should not be systemic"

    def test_systemic_symptoms(self):
        systemic = [
            Symptom.MOOD_CRASH,
            Symptom.BRAIN_FOG,
            Symptom.INSOMNIA,
        ]
        for symptom in systemic:
            assert symptom.is_systemic() is True, f"{symptom} should be systemic"
            assert symptom.is_physical() is False, f"{symptom} should not be physical"

    def test_other_is_neither_physical_nor_systemic(self):
        assert Symptom.OTHER.is_physical() is False
        assert Symptom.OTHER.is_systemic() is False

    def test_no_symptom_is_both_physical_and_systemic(self):
        for symptom in Symptom:
            assert not (symptom.is_physical() and symptom.is_systemic()), (
                f"{symptom} cannot be both physical and systemic"
            )

    def test_symptom_is_string_enum(self):
        # Ensures clean JSON serialisation
        assert Symptom.PELVIC_PAIN == "pelvic_pain"

    def test_symptom_count_is_stable(self):
        # This test is intentionally strict.
        # If you add or remove a symptom, this test will fail and force
        # you to think about the impact on historical data.
        assert len(Symptom) == 11
