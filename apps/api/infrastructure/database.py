"""
infrastructure.database

SQLAlchemy engine and session management.

The engine is created once from DATABASE_URL and shared across
the process. Sessions are short-lived — one per request in the
API, one per use case call in background workers.

Usage in FastAPI:
    from infrastructure.database import get_db
    from sqlalchemy.orm import Session

    @router.post("/logs")
    def create_log(db: Session = Depends(get_db)):
        ...

Usage in tests:
    Use the InMemory fakes instead. Integration tests that need a
    real session should use the test fixtures in
    tests/integration/conftest.py.

Environment variables:
    DATABASE_URL — full SQLAlchemy connection string.
    Example: postgresql+psycopg2://user:password@localhost:5432/endomatrix

    DATABASE_POOL_SIZE — connection pool size. Default: 5.
    DATABASE_MAX_OVERFLOW — max connections above pool size. Default: 10.
"""

from __future__ import annotations

import os
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

def _build_engine() -> Engine:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL environment variable is not set. "
            "Set it to a valid PostgreSQL connection string before starting."
        )

    pool_size = int(os.environ.get("DATABASE_POOL_SIZE", "5"))
    max_overflow = int(os.environ.get("DATABASE_MAX_OVERFLOW", "10"))

    return create_engine(
        url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,   # Detect stale connections before use
        echo=os.environ.get("DATABASE_ECHO", "false").lower() == "true",
    )


# Module-level engine — created lazily on first import in production.
# Tests that need a real DB create their own engine via create_test_engine().
_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = _build_engine()
    return _engine


def create_test_engine(url: str) -> Engine:
    """
    Create a standalone engine for integration tests.

    Tests should use this instead of get_engine() so they can
    point at a separate test database without touching the
    module-level singleton.
    """
    return create_engine(url, echo=False)


# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------

def _make_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,  # Domain objects should not expire after commit
    )


_SessionLocal: sessionmaker | None = None


def get_session_factory() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = _make_session_factory(get_engine())
    return _SessionLocal


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a database session per request.

    The session is committed if no exception is raised.
    It is rolled back and closed on any exception.

    Usage:
        @router.post("/logs")
        def create_log(db: Session = Depends(get_db)):
            ...
    """
    factory = get_session_factory()
    db = factory()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

def check_database_connection() -> bool:
    """
    Return True if the database is reachable. Used for health check endpoints.
    Does not raise — returns False on any failure.
    """
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
