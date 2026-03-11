"""
use_cases.pattern

GeneratePattern    — runs the pattern engine and saves the result
GetPatternSummary  — fetches the latest PatternResult for the Insights screen

GeneratePattern is triggered by the presentation layer when
LogDailyEntry returns insight_threshold_crossed=True, or on a
schedule to keep patterns current as more logs accumulate.

It is intentionally separate from LogDailyEntry. Keeping them
decoupled means:
- Pattern generation can be retried independently if it fails
- It can be run as a background job without blocking the log response
- Tests for each use case are isolated and focused
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from application.base import Command, Result
from application.use_cases.log_daily_entry import INSIGHT_UNLOCK_THRESHOLD
from domain.engine.pattern_engine import PatternEngine, MIN_LOGS_FOR_PATTERN
from domain.models.events import PatternGenerated
from domain.models.pattern import PatternResult
from domain.ports import IEventPublisher, ILogRepository, IPatternRepository
from datetime import datetime


# ---------------------------------------------------------------------------
# GeneratePattern
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GeneratePatternCommand(Command):
    user_id: UUID


@dataclass(frozen=True)
class GeneratePatternResult(Result):
    pattern: Optional[PatternResult]
    was_generated: bool
    """
    False if not enough logs exist to generate a pattern.
    The caller should not treat this as an error.
    """
    is_first_pattern: bool
    """
    True if this is the first pattern ever generated for this user.
    The presentation layer uses this to show the 30-day unlock moment.
    """


class GeneratePattern:
    """
    Loads all logs for a user, runs the PatternEngine, and saves the result.

    If not enough logs exist (fewer than MIN_LOGS_FOR_PATTERN),
    returns was_generated=False without raising.

    Raises:
        Nothing. All failure modes are expressed in the result.
    """

    def __init__(
        self,
        log_repo: ILogRepository,
        pattern_repo: IPatternRepository,
        event_publisher: IEventPublisher,
        pattern_engine: Optional[PatternEngine] = None,
    ) -> None:
        self._log_repo = log_repo
        self._pattern_repo = pattern_repo
        self._event_publisher = event_publisher
        self._engine = pattern_engine or PatternEngine()

    def execute(self, command: GeneratePatternCommand) -> GeneratePatternResult:
        logs = self._log_repo.get_logs_for_user(command.user_id)

        if len(logs) < MIN_LOGS_FOR_PATTERN:
            return GeneratePatternResult(
                pattern=None,
                was_generated=False,
                is_first_pattern=False,
            )

        # Logs must be sorted ascending for the engine
        sorted_logs = sorted(logs, key=lambda l: l.logged_date)

        pattern = self._engine.analyze(sorted_logs)

        if pattern is None:
            return GeneratePatternResult(
                pattern=None,
                was_generated=False,
                is_first_pattern=False,
            )

        is_first = self._pattern_repo.count_patterns(command.user_id) == 0

        self._pattern_repo.save_pattern(pattern)

        self._event_publisher.publish(PatternGenerated(
            user_id=command.user_id,
            occurred_at=datetime.utcnow(),
            pattern_id=pattern.id,
            cycles_analyzed=pattern.cycles_analyzed,
            total_logs=pattern.total_logs,
            is_first=is_first,
        ))

        return GeneratePatternResult(
            pattern=pattern,
            was_generated=True,
            is_first_pattern=is_first,
        )


# ---------------------------------------------------------------------------
# GetPatternSummary
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GetPatternSummaryCommand(Command):
    user_id: UUID


@dataclass(frozen=True)
class GetPatternSummaryResult(Result):
    pattern: Optional[PatternResult]
    log_count: int
    logs_until_unlock: int
    is_unlocked: bool
    """
    True if the user has reached the 30-log threshold and a pattern exists.
    False means show the teaser state on the Insights screen.
    """


class GetPatternSummary:
    """
    Returns the latest PatternResult along with unlock state.

    Used by the Insights screen to decide whether to show the
    teaser or the full pattern page.
    """

    def __init__(
        self,
        log_repo: ILogRepository,
        pattern_repo: IPatternRepository,
    ) -> None:
        self._log_repo = log_repo
        self._pattern_repo = pattern_repo

    def execute(self, command: GetPatternSummaryCommand) -> GetPatternSummaryResult:
        log_count = self._log_repo.count_logs_for_user(command.user_id)
        pattern = self._pattern_repo.get_latest_pattern(command.user_id)

        logs_until_unlock = max(0, INSIGHT_UNLOCK_THRESHOLD - log_count)
        is_unlocked = log_count >= INSIGHT_UNLOCK_THRESHOLD and pattern is not None

        return GetPatternSummaryResult(
            pattern=pattern,
            log_count=log_count,
            logs_until_unlock=logs_until_unlock,
            is_unlocked=is_unlocked,
        )
