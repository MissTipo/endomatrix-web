"""
tests/presentation/test_app.py

Tests for the FastAPI app itself — health endpoint and error handler wiring.
These do not test individual routers but confirm the app boots correctly
and the cross-cutting concerns work end to end.
"""

from __future__ import annotations

from presentation.app import create_app
from fastapi.testclient import TestClient


def test_health_returns_200():
    client = TestClient(create_app(), raise_server_exceptions=False)
    resp = client.get("/health")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_unregistered_route_returns_404():
    client = TestClient(create_app(), raise_server_exceptions=False)
    resp = client.get("/does-not-exist")

    assert resp.status_code == 404


def test_openapi_schema_available():
    client = TestClient(create_app(), raise_server_exceptions=False)
    resp = client.get("/openapi.json")

    assert resp.status_code == 200
    schema = resp.json()
    assert "EndoMatrix API" in schema["info"]["title"]


def test_docs_available():
    client = TestClient(create_app(), raise_server_exceptions=False)
    resp = client.get("/docs")

    assert resp.status_code == 200
