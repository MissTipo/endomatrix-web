"""
tests/integration/conftest.py

Test fixtures for infrastructure integration tests.

These tests require a running PostgreSQL database. They are skipped
automatically if TEST_DATABASE_URL is not set.

To run integration tests locally:
    TEST_DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/endomatrix_test \
    pytest tests/integration/ -v

Each test gets a fresh database session and a clean schema. Tables are
created before the test and dropped after, so tests are fully isolated
from each other.

The session is NOT committed between tests. Each test runs inside a
transaction that is rolled back at teardown — much faster than
recreating tables for every test.
"""

import os

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from infrastructure.database import create_test_engine
from infrastructure.orm.tables import metadata

from pathlib import Path
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
except ImportError:
    pass


def _get_test_url() -> str | None:
    return os.environ.get("TEST_DATABASE_URL")


# Skip the entire integration suite if no test DB is available
def pytest_collection_modifyitems(items):
    if _get_test_url():
        return
    skip = pytest.mark.skip(reason="TEST_DATABASE_URL not set")
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker(skip)


@pytest.fixture(scope="session")
def test_engine():
    url = _get_test_url()
    if not url:
        pytest.skip("TEST_DATABASE_URL not set")
    engine = create_test_engine(url)
    metadata.create_all(engine)
    yield engine
    metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def db_session(test_engine) -> Session:
    """
    Yields a session that is rolled back after each test.

    This means no test leaves data behind, and the database
    stays clean without dropping and recreating tables.
    """
    connection = test_engine.connect()
    transaction = connection.begin()

    from sqlalchemy.orm import sessionmaker
    factory = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = factory()

    yield session

    session.close()
    transaction.rollback()
    connection.close()
