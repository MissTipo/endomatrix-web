"""
tests/presentation/conftest.py

Shared fixtures for presentation layer tests.

Strategy:
    We test the HTTP layer in isolation — routing, serialization,
    validation, error mapping. Use case logic is already tested in
    tests/application/. Here we mock use cases entirely with
    unittest.mock.MagicMock and assert on what the router does with
    their return values and exceptions.

    dependency_overrides is reset after every test via autouse teardown
    so overrides never bleed between tests.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from infrastructure.database import get_db
from presentation.app import app


USER_ID = uuid.uuid4()
USER_ID_STR = str(USER_ID)

# Standard headers used in every authenticated request
AUTH_HEADERS = {"X-User-Id": USER_ID_STR}


@pytest.fixture(autouse=True)
def override_get_db():
    """
    Prevent get_db from trying to build a real database engine.
    Tests that need a real session use the integration test suite instead.
    """
    fake_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: fake_db
    yield
    # override_cleanup handles clearing all overrides after each test


@pytest.fixture(scope="session")
def client() -> TestClient:
    """
    A single TestClient for the session.

    dependency_overrides are set per-test and cleaned up by the
    override_cleanup autouse fixture below.
    """
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def override_cleanup():
    """
    Reset dependency_overrides after every test.

    Without this, an override set in one test leaks into the next.
    """
    yield
    app.dependency_overrides.clear()


def mock_use_case(return_value: Any = None, raises: Exception | None = None) -> MagicMock:
    """
    Build a mock use case whose .execute() either returns a value or raises.

    Usage:
        uc = mock_use_case(return_value=some_result)
        uc = mock_use_case(raises=ValueError("bad input"))
    """
    mock = MagicMock()
    if raises is not None:
        mock.execute.side_effect = raises
    else:
        mock.execute.return_value = return_value
    return mock
