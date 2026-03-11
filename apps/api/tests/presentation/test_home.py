"""
tests/presentation/test_home.py

Tests for GET /home.

What we are testing:
    - 200 on success
    - Response body contains all expected fields
    - Null-safe fields (current_cycle_day, current_phase, early_feedback) when absent
    - Missing header → 401
    - Unexpected use case failure → 500
"""

from __future__ import annotations

from application.use_cases import HomeState
from presentation.dependencies import get_home_state_use_case
from presentation.app import app
from tests.presentation.conftest import AUTH_HEADERS, mock_use_case


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _home_state(**overrides) -> HomeState:
    defaults = dict(
        has_logged_today=False,
        log_count=5,
        current_cycle_day=14,
        current_phase="Luteal",
        phase_is_reliable=True,
        streak=5,
        logs_until_unlock=25,
        is_insights_unlocked=False,
        early_feedback=None,
    )
    return HomeState(**{**defaults, **overrides})


# ---------------------------------------------------------------------------
# GET /home
# ---------------------------------------------------------------------------

class TestGetHome:

    def test_returns_200(self, client):
        uc = mock_use_case(return_value=_home_state())
        app.dependency_overrides[get_home_state_use_case] = lambda: uc

        resp = client.get("/home", headers=AUTH_HEADERS)

        assert resp.status_code == 200

    def test_response_contains_all_fields(self, client):
        uc = mock_use_case(return_value=_home_state())
        app.dependency_overrides[get_home_state_use_case] = lambda: uc

        body = client.get("/home", headers=AUTH_HEADERS).json()

        assert "has_logged_today" in body
        assert "log_count" in body
        assert "current_cycle_day" in body
        assert "current_phase" in body
        assert "phase_is_reliable" in body
        assert "streak" in body
        assert "logs_until_unlock" in body
        assert "is_insights_unlocked" in body
        assert "early_feedback" in body

    def test_field_values_match_use_case_output(self, client):
        state = _home_state(
            has_logged_today=True,
            log_count=12,
            current_cycle_day=7,
            current_phase="Follicular",
            streak=12,
            logs_until_unlock=18,
        )
        uc = mock_use_case(return_value=state)
        app.dependency_overrides[get_home_state_use_case] = lambda: uc

        body = client.get("/home", headers=AUTH_HEADERS).json()

        assert body["has_logged_today"] is True
        assert body["log_count"] == 12
        assert body["current_cycle_day"] == 7
        assert body["current_phase"] == "Follicular"
        assert body["streak"] == 12
        assert body["logs_until_unlock"] == 18

    def test_null_phase_when_no_baseline(self, client):
        state = _home_state(
            current_cycle_day=None,
            current_phase=None,
            phase_is_reliable=False,
        )
        uc = mock_use_case(return_value=state)
        app.dependency_overrides[get_home_state_use_case] = lambda: uc

        body = client.get("/home", headers=AUTH_HEADERS).json()

        assert body["current_cycle_day"] is None
        assert body["current_phase"] is None
        assert body["phase_is_reliable"] is False

    def test_early_feedback_message_returned_when_present(self, client):
        state = _home_state(
            early_feedback="You tend to log higher pain around this point in your cycle."
        )
        uc = mock_use_case(return_value=state)
        app.dependency_overrides[get_home_state_use_case] = lambda: uc

        body = client.get("/home", headers=AUTH_HEADERS).json()

        assert body["early_feedback"] == "You tend to log higher pain around this point in your cycle."

    def test_insights_unlocked_state_reflected(self, client):
        state = _home_state(
            log_count=30,
            logs_until_unlock=0,
            is_insights_unlocked=True,
        )
        uc = mock_use_case(return_value=state)
        app.dependency_overrides[get_home_state_use_case] = lambda: uc

        body = client.get("/home", headers=AUTH_HEADERS).json()

        assert body["is_insights_unlocked"] is True
        assert body["logs_until_unlock"] == 0

    def test_missing_header_returns_401_or_422(self, client):
        resp = client.get("/home")

        assert resp.status_code in (401, 422)

    def test_invalid_uuid_returns_401(self, client):
        resp = client.get("/home", headers={"X-User-Id": "not-a-uuid"})

        assert resp.status_code == 401

    def test_unhandled_exception_returns_500(self, client):
        uc = mock_use_case(raises=RuntimeError("unexpected"))
        app.dependency_overrides[get_home_state_use_case] = lambda: uc

        resp = client.get("/home", headers=AUTH_HEADERS)

        assert resp.status_code == 500
