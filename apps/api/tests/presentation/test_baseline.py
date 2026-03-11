"""
tests/presentation/test_baseline.py

Tests for POST /baseline and PUT /baseline.

What we are testing:
    - Correct status codes on happy paths
    - Response body is shaped correctly from domain objects
    - ValueError from the use case maps to 400
    - Missing or invalid X-User-Id maps to 401
    - Pydantic validates the request body (future date → 422)
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from unittest.mock import MagicMock

import pytest

from application.use_cases import (
    SetCycleBaselineResult,
    UpdateCycleBaselineResult,
)
from domain.models.cycle import CycleBaseline
from presentation.dependencies import (
    get_set_cycle_baseline_use_case,
    get_update_cycle_baseline_use_case,
)
from presentation.app import app
from tests.presentation.conftest import AUTH_HEADERS, USER_ID, mock_use_case


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_baseline(
    *,
    user_id=None,
    average_cycle_length: int | None = 28,
    is_irregular: bool = False,
) -> CycleBaseline:
    return CycleBaseline(
        user_id=user_id or USER_ID,
        last_period_start=date(2026, 2, 1),
        average_cycle_length=average_cycle_length,
        is_irregular=is_irregular,
        updated_at=datetime(2026, 2, 1, 12, 0, 0),
    )


VALID_BODY = {
    "last_period_start": "2026-02-01",
    "average_cycle_length": 28,
    "is_irregular": False,
}


# ---------------------------------------------------------------------------
# POST /baseline
# ---------------------------------------------------------------------------

class TestSetBaseline:

    def test_returns_201_on_success(self, client):
        baseline = _make_baseline()
        uc = mock_use_case(return_value=SetCycleBaselineResult(baseline=baseline))
        app.dependency_overrides[get_set_cycle_baseline_use_case] = lambda: uc

        resp = client.post("/baseline", json=VALID_BODY, headers=AUTH_HEADERS)

        assert resp.status_code == 201

    def test_response_contains_expected_fields(self, client):
        baseline = _make_baseline()
        uc = mock_use_case(return_value=SetCycleBaselineResult(baseline=baseline))
        app.dependency_overrides[get_set_cycle_baseline_use_case] = lambda: uc

        resp = client.post("/baseline", json=VALID_BODY, headers=AUTH_HEADERS)
        body = resp.json()

        assert body["user_id"] == str(USER_ID)
        assert body["last_period_start"] == "2026-02-01"
        assert body["average_cycle_length"] == 28
        assert body["is_irregular"] is False
        assert "updated_at" in body
        assert "has_reliable_baseline" in body

    def test_has_reliable_baseline_true_when_length_known(self, client):
        baseline = _make_baseline(average_cycle_length=28)
        uc = mock_use_case(return_value=SetCycleBaselineResult(baseline=baseline))
        app.dependency_overrides[get_set_cycle_baseline_use_case] = lambda: uc

        resp = client.post("/baseline", json=VALID_BODY, headers=AUTH_HEADERS)

        assert resp.json()["has_reliable_baseline"] is True

    def test_has_reliable_baseline_false_when_irregular(self, client):
        baseline = _make_baseline(average_cycle_length=None, is_irregular=True)
        uc = mock_use_case(return_value=SetCycleBaselineResult(baseline=baseline))
        app.dependency_overrides[get_set_cycle_baseline_use_case] = lambda: uc

        body = {**VALID_BODY, "average_cycle_length": None, "is_irregular": True}
        resp = client.post("/baseline", json=body, headers=AUTH_HEADERS)

        assert resp.json()["has_reliable_baseline"] is False

    def test_use_case_called_with_correct_command(self, client):
        baseline = _make_baseline()
        uc = mock_use_case(return_value=SetCycleBaselineResult(baseline=baseline))
        app.dependency_overrides[get_set_cycle_baseline_use_case] = lambda: uc

        client.post("/baseline", json=VALID_BODY, headers=AUTH_HEADERS)

        uc.execute.assert_called_once()
        cmd = uc.execute.call_args[0][0]
        assert cmd.user_id == USER_ID
        assert cmd.average_cycle_length == 28
        assert cmd.is_irregular is False

    def test_value_error_returns_400(self, client):
        uc = mock_use_case(raises=ValueError("Baseline already exists."))
        app.dependency_overrides[get_set_cycle_baseline_use_case] = lambda: uc

        resp = client.post("/baseline", json=VALID_BODY, headers=AUTH_HEADERS)

        assert resp.status_code == 400
        assert "Baseline already exists." in resp.json()["detail"]

    def test_missing_user_id_header_returns_401(self, client):
        resp = client.post("/baseline", json=VALID_BODY)

        assert resp.status_code in (401, 422)

    def test_invalid_user_id_header_returns_401(self, client):
        resp = client.post(
            "/baseline",
            json=VALID_BODY,
            headers={"X-User-Id": "not-a-uuid"},
        )

        assert resp.status_code == 401

    def test_future_last_period_start_returns_422(self, client):
        uc = mock_use_case(return_value=SetCycleBaselineResult(baseline=_make_baseline()))
        app.dependency_overrides[get_set_cycle_baseline_use_case] = lambda: uc

        body = {**VALID_BODY, "last_period_start": "2099-01-01"}
        resp = client.post("/baseline", json=body, headers=AUTH_HEADERS)

        assert resp.status_code == 422

    def test_cycle_length_below_21_returns_422(self, client):
        body = {**VALID_BODY, "average_cycle_length": 20}
        resp = client.post("/baseline", json=body, headers=AUTH_HEADERS)

        assert resp.status_code == 422

    def test_cycle_length_above_45_returns_422(self, client):
        body = {**VALID_BODY, "average_cycle_length": 46}
        resp = client.post("/baseline", json=body, headers=AUTH_HEADERS)

        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# PUT /baseline
# ---------------------------------------------------------------------------

class TestUpdateBaseline:

    def test_returns_200_on_success(self, client):
        baseline = _make_baseline()
        uc = mock_use_case(return_value=UpdateCycleBaselineResult(baseline=baseline))
        app.dependency_overrides[get_update_cycle_baseline_use_case] = lambda: uc

        resp = client.put("/baseline", json=VALID_BODY, headers=AUTH_HEADERS)

        assert resp.status_code == 200

    def test_response_shape_matches_set_baseline(self, client):
        baseline = _make_baseline()
        uc = mock_use_case(return_value=UpdateCycleBaselineResult(baseline=baseline))
        app.dependency_overrides[get_update_cycle_baseline_use_case] = lambda: uc

        resp = client.put("/baseline", json=VALID_BODY, headers=AUTH_HEADERS)
        body = resp.json()

        assert body["user_id"] == str(USER_ID)
        assert body["average_cycle_length"] == 28

    def test_value_error_returns_400(self, client):
        uc = mock_use_case(raises=ValueError("No baseline to update."))
        app.dependency_overrides[get_update_cycle_baseline_use_case] = lambda: uc

        resp = client.put("/baseline", json=VALID_BODY, headers=AUTH_HEADERS)

        assert resp.status_code == 400

    def test_use_case_called_with_correct_user_id(self, client):
        baseline = _make_baseline()
        uc = mock_use_case(return_value=UpdateCycleBaselineResult(baseline=baseline))
        app.dependency_overrides[get_update_cycle_baseline_use_case] = lambda: uc

        client.put("/baseline", json=VALID_BODY, headers=AUTH_HEADERS)

        cmd = uc.execute.call_args[0][0]
        assert cmd.user_id == USER_ID
