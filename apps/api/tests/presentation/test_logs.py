"""
tests/presentation/test_logs.py

Tests for POST /logs.

What we are testing:
    - 201 on success
    - Response body maps DailyLog fields correctly
    - message is "Saved." for new logs and "Updated." for superseded ones
    - insight_threshold_crossed=True causes GeneratePattern to be called
    - GeneratePattern failure does NOT cause the log response to fail
    - Future logged_date → 422
    - Pain/energy out of range → 422
    - Unknown dominant_symptom → 422
    - Missing header → 401
    - ValueError from LogDailyEntry (no baseline) → 400
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest

from application.use_cases import (
    GeneratePatternResult,
    LogDailyEntryResult,
)
from domain.models.cycle import CyclePhase, Score
from domain.models.daily_log import DailyLog
from domain.models.symptom import Symptom
from presentation.dependencies import (
    get_generate_pattern_use_case,
    get_log_daily_entry_use_case,
)
from presentation.app import app
from tests.presentation.conftest import AUTH_HEADERS, USER_ID, mock_use_case


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_log(
    *,
    pain_level: int = 6,
    energy_level: int = 4,
    was_superseded: bool = False,
) -> DailyLog:
    return DailyLog(
        id=uuid.uuid4(),
        user_id=USER_ID,
        logged_date=date(2026, 3, 11),
        pain_level=Score(pain_level),
        energy_level=Score(energy_level),
        dominant_symptom=Symptom.PELVIC_PAIN,
        cycle_day=14,
        cycle_phase=CyclePhase.LUTEAL,
        created_at=datetime(2026, 3, 11, 9, 0, 0),
    )


def _log_result(
    *,
    log_count: int = 5,
    insight_threshold_crossed: bool = False,
    was_superseded: bool = False,
) -> LogDailyEntryResult:
    return LogDailyEntryResult(
        log=_make_log(was_superseded=was_superseded),
        log_count=log_count,
        insight_threshold_crossed=insight_threshold_crossed,
        was_superseded=was_superseded,
    )


def _pattern_result(*, was_generated: bool = True) -> GeneratePatternResult:
    return GeneratePatternResult(
        pattern=None,
        was_generated=was_generated,
        is_first_pattern=was_generated,
    )


VALID_BODY = {
    "logged_date": "2026-03-11",
    "pain_level": 6,
    "energy_level": 4,
    "dominant_symptom": "pelvic_pain",
}


# ---------------------------------------------------------------------------
# POST /logs — happy path
# ---------------------------------------------------------------------------

class TestSubmitLog:

    def test_returns_201_on_success(self, client):
        log_uc = mock_use_case(return_value=_log_result())
        pattern_uc = mock_use_case(return_value=_pattern_result())
        app.dependency_overrides[get_log_daily_entry_use_case] = lambda: log_uc
        app.dependency_overrides[get_generate_pattern_use_case] = lambda: pattern_uc

        resp = client.post("/logs", json=VALID_BODY, headers=AUTH_HEADERS)

        assert resp.status_code == 201

    def test_response_fields_present(self, client):
        log_uc = mock_use_case(return_value=_log_result())
        pattern_uc = mock_use_case(return_value=_pattern_result())
        app.dependency_overrides[get_log_daily_entry_use_case] = lambda: log_uc
        app.dependency_overrides[get_generate_pattern_use_case] = lambda: pattern_uc

        resp = client.post("/logs", json=VALID_BODY, headers=AUTH_HEADERS)
        body = resp.json()

        assert "log_id" in body
        assert body["logged_date"] == "2026-03-11"
        assert body["cycle_day"] == 14
        assert body["cycle_phase"] == CyclePhase.LUTEAL.display_name
        assert body["pain_level"] == 6
        assert body["energy_level"] == 4
        assert body["dominant_symptom"] == Symptom.PELVIC_PAIN.value
        assert body["log_count"] == 5
        assert body["was_superseded"] is False
        assert body["insight_threshold_crossed"] is False

    def test_message_is_saved_for_new_log(self, client):
        log_uc = mock_use_case(return_value=_log_result(was_superseded=False))
        pattern_uc = mock_use_case(return_value=_pattern_result())
        app.dependency_overrides[get_log_daily_entry_use_case] = lambda: log_uc
        app.dependency_overrides[get_generate_pattern_use_case] = lambda: pattern_uc

        resp = client.post("/logs", json=VALID_BODY, headers=AUTH_HEADERS)

        assert resp.json()["message"] == "Saved."

    def test_message_is_updated_for_superseded_log(self, client):
        log_uc = mock_use_case(return_value=_log_result(was_superseded=True))
        pattern_uc = mock_use_case(return_value=_pattern_result())
        app.dependency_overrides[get_log_daily_entry_use_case] = lambda: log_uc
        app.dependency_overrides[get_generate_pattern_use_case] = lambda: pattern_uc

        resp = client.post("/logs", json=VALID_BODY, headers=AUTH_HEADERS)

        assert resp.json()["message"] == "Updated."

    def test_use_case_called_with_correct_command(self, client):
        log_uc = mock_use_case(return_value=_log_result())
        pattern_uc = mock_use_case(return_value=_pattern_result())
        app.dependency_overrides[get_log_daily_entry_use_case] = lambda: log_uc
        app.dependency_overrides[get_generate_pattern_use_case] = lambda: pattern_uc

        client.post("/logs", json=VALID_BODY, headers=AUTH_HEADERS)

        cmd = log_uc.execute.call_args[0][0]
        assert cmd.user_id == USER_ID
        assert cmd.pain_level == 6
        assert cmd.energy_level == 4
        assert cmd.dominant_symptom == Symptom.PELVIC_PAIN


# ---------------------------------------------------------------------------
# Pattern generation trigger
# ---------------------------------------------------------------------------

class TestPatternGenerationTrigger:

    def test_generate_pattern_called_when_threshold_crossed(self, client):
        log_uc = mock_use_case(
            return_value=_log_result(log_count=30, insight_threshold_crossed=True)
        )
        pattern_uc = mock_use_case(return_value=_pattern_result())
        app.dependency_overrides[get_log_daily_entry_use_case] = lambda: log_uc
        app.dependency_overrides[get_generate_pattern_use_case] = lambda: pattern_uc

        resp = client.post("/logs", json=VALID_BODY, headers=AUTH_HEADERS)

        assert resp.status_code == 201
        pattern_uc.execute.assert_called_once()

    def test_generate_pattern_not_called_before_threshold(self, client):
        log_uc = mock_use_case(
            return_value=_log_result(log_count=5, insight_threshold_crossed=False)
        )
        pattern_uc = mock_use_case(return_value=_pattern_result())
        app.dependency_overrides[get_log_daily_entry_use_case] = lambda: log_uc
        app.dependency_overrides[get_generate_pattern_use_case] = lambda: pattern_uc

        client.post("/logs", json=VALID_BODY, headers=AUTH_HEADERS)

        pattern_uc.execute.assert_not_called()

    def test_log_succeeds_even_if_pattern_generation_raises(self, client):
        log_uc = mock_use_case(
            return_value=_log_result(log_count=30, insight_threshold_crossed=True)
        )
        pattern_uc = mock_use_case(raises=RuntimeError("DB timeout"))
        app.dependency_overrides[get_log_daily_entry_use_case] = lambda: log_uc
        app.dependency_overrides[get_generate_pattern_use_case] = lambda: pattern_uc

        resp = client.post("/logs", json=VALID_BODY, headers=AUTH_HEADERS)

        # Log is still saved; pattern failure is swallowed
        assert resp.status_code == 201


# ---------------------------------------------------------------------------
# Validation and error cases
# ---------------------------------------------------------------------------

class TestLogValidation:

    def test_value_error_returns_400(self, client):
        log_uc = mock_use_case(raises=ValueError("No cycle baseline found."))
        pattern_uc = mock_use_case(return_value=_pattern_result())
        app.dependency_overrides[get_log_daily_entry_use_case] = lambda: log_uc
        app.dependency_overrides[get_generate_pattern_use_case] = lambda: pattern_uc

        resp = client.post("/logs", json=VALID_BODY, headers=AUTH_HEADERS)

        assert resp.status_code == 400
        assert "No cycle baseline found." in resp.json()["detail"]

    def test_future_logged_date_returns_422(self, client):
        body = {**VALID_BODY, "logged_date": "2099-12-31"}
        resp = client.post("/logs", json=body, headers=AUTH_HEADERS)

        assert resp.status_code == 422

    def test_pain_level_above_10_returns_422(self, client):
        body = {**VALID_BODY, "pain_level": 11}
        resp = client.post("/logs", json=body, headers=AUTH_HEADERS)

        assert resp.status_code == 422

    def test_energy_level_below_0_returns_422(self, client):
        body = {**VALID_BODY, "energy_level": -1}
        resp = client.post("/logs", json=body, headers=AUTH_HEADERS)

        assert resp.status_code == 422

    def test_unknown_symptom_returns_422(self, client):
        body = {**VALID_BODY, "dominant_symptom": "fever"}
        resp = client.post("/logs", json=body, headers=AUTH_HEADERS)

        assert resp.status_code == 422

    def test_missing_user_id_header_returns_401_or_422(self, client):
        resp = client.post("/logs", json=VALID_BODY)

        assert resp.status_code in (401, 422)

    def test_invalid_uuid_header_returns_401(self, client):
        resp = client.post(
            "/logs",
            json=VALID_BODY,
            headers={"X-User-Id": "not-a-uuid"},
        )

        assert resp.status_code == 401

    def test_optional_mood_and_note_accepted(self, client):
        log_uc = mock_use_case(return_value=_log_result())
        pattern_uc = mock_use_case(return_value=_pattern_result())
        app.dependency_overrides[get_log_daily_entry_use_case] = lambda: log_uc
        app.dependency_overrides[get_generate_pattern_use_case] = lambda: pattern_uc

        body = {**VALID_BODY, "mood_level": 7, "note": "Rough day."}
        resp = client.post("/logs", json=body, headers=AUTH_HEADERS)

        assert resp.status_code == 201
        cmd = log_uc.execute.call_args[0][0]
        assert cmd.mood_level == 7
        assert cmd.note == "Rough day."

    def test_note_above_280_chars_returns_422(self, client):
        body = {**VALID_BODY, "note": "x" * 281}
        resp = client.post("/logs", json=body, headers=AUTH_HEADERS)

        assert resp.status_code == 422
