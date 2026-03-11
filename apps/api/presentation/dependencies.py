"""
presentation.dependencies

FastAPI dependency functions that wire infrastructure implementations
to application use cases.

Every endpoint declares its use case as a dependency. FastAPI resolves
the dependency graph, creates one db session per request, builds the
repos and use case, runs the handler, then commits or rolls back.

User identity:
    User ID is read from the X-User-Id request header for now.
    This is a deliberate placeholder — when Clerk auth is added,
    this single function is the only thing that changes.
    All routers call get_current_user_id() without knowing how
    the ID is resolved.

Usage in a router:
    @router.get("/home")
    def get_home(
        use_case: GetHomeState = Depends(get_home_state_use_case),
        user_id: UUID = Depends(get_current_user_id),
    ):
        ...
"""

from __future__ import annotations

from uuid import UUID

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from application.use_cases import (
    GenerateEarlyFeedback,
    GeneratePattern,
    GetHomeState,
    GetPatternSummary,
    LogDailyEntry,
    SetCycleBaseline,
    UpdateCycleBaseline,
)
from infrastructure.database import get_db
from infrastructure.events.publisher import DatabaseEventPublisher
from infrastructure.repositories.cycle_repository import PostgresCycleRepository
from infrastructure.repositories.log_repository import PostgresLogRepository
from infrastructure.repositories.pattern_repository import PostgresPatternRepository


# ---------------------------------------------------------------------------
# User identity
# ---------------------------------------------------------------------------

def get_current_user_id(x_user_id: str = Header(...)) -> UUID:
    """
    Extract the authenticated user's ID from the X-User-Id header.

    Raises 401 if the header is missing or not a valid UUID.

    This is a placeholder. When Clerk auth is wired, replace this
    with JWT verification and extract the user ID from the token claims.
    """
    try:
        return UUID(x_user_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=401, detail="Invalid or missing X-User-Id header.")


# ---------------------------------------------------------------------------
# Repository factory helpers
# ---------------------------------------------------------------------------

def get_log_repo(db: Session = Depends(get_db)) -> PostgresLogRepository:
    return PostgresLogRepository(db)


def get_cycle_repo(db: Session = Depends(get_db)) -> PostgresCycleRepository:
    return PostgresCycleRepository(db)


def get_pattern_repo(db: Session = Depends(get_db)) -> PostgresPatternRepository:
    return PostgresPatternRepository(db)


def get_event_publisher(db: Session = Depends(get_db)) -> DatabaseEventPublisher:
    return DatabaseEventPublisher(db)


# ---------------------------------------------------------------------------
# Use case factories
# ---------------------------------------------------------------------------

def get_set_cycle_baseline_use_case(
    cycle_repo: PostgresCycleRepository = Depends(get_cycle_repo),
    publisher: DatabaseEventPublisher = Depends(get_event_publisher),
) -> SetCycleBaseline:
    return SetCycleBaseline(cycle_repo, publisher)


def get_update_cycle_baseline_use_case(
    cycle_repo: PostgresCycleRepository = Depends(get_cycle_repo),
    publisher: DatabaseEventPublisher = Depends(get_event_publisher),
) -> UpdateCycleBaseline:
    return UpdateCycleBaseline(cycle_repo, publisher)


def get_log_daily_entry_use_case(
    log_repo: PostgresLogRepository = Depends(get_log_repo),
    cycle_repo: PostgresCycleRepository = Depends(get_cycle_repo),
    publisher: DatabaseEventPublisher = Depends(get_event_publisher),
) -> LogDailyEntry:
    return LogDailyEntry(log_repo, cycle_repo, publisher)


def get_home_state_use_case(
    log_repo: PostgresLogRepository = Depends(get_log_repo),
    cycle_repo: PostgresCycleRepository = Depends(get_cycle_repo),
    pattern_repo: PostgresPatternRepository = Depends(get_pattern_repo),
) -> GetHomeState:
    return GetHomeState(log_repo, cycle_repo, pattern_repo)


def get_pattern_summary_use_case(
    log_repo: PostgresLogRepository = Depends(get_log_repo),
    pattern_repo: PostgresPatternRepository = Depends(get_pattern_repo),
) -> GetPatternSummary:
    return GetPatternSummary(log_repo, pattern_repo)


def get_generate_pattern_use_case(
    log_repo: PostgresLogRepository = Depends(get_log_repo),
    pattern_repo: PostgresPatternRepository = Depends(get_pattern_repo),
    publisher: DatabaseEventPublisher = Depends(get_event_publisher),
) -> GeneratePattern:
    return GeneratePattern(log_repo, pattern_repo, publisher)


def get_generate_early_feedback_use_case(
    log_repo: PostgresLogRepository = Depends(get_log_repo),
    pattern_repo: PostgresPatternRepository = Depends(get_pattern_repo),
    publisher: DatabaseEventPublisher = Depends(get_event_publisher),
) -> GenerateEarlyFeedback:
    return GenerateEarlyFeedback(log_repo, pattern_repo, publisher)
