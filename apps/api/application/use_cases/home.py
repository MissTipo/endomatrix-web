"""
use_cases.home

GetHomeState          — everything the Home screen needs in one call
GenerateEarlyFeedback — generates the reinforcement card for the Home screen

GetHomeState is a read-only use case. It loads and assembles state
from multiple repositories without writing anything. It exists because
the Home screen needs several pieces of information at once and we do
not want the presentation layer making multiple repository calls directly.

GenerateEarlyFeedback is a write use case. It runs the engine's feedback
logic and saves the result. It is triggered on a schedule every 5–7 days
during the day 7–30 window, not on every Home screen load.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from application.base import Command, Result
from domain.engine.pattern_engine import PatternEngine, MIN_LOGS_FOR_FEEDBACK
from domain.engine.phase_calculator import PhaseCalculator, PhaseResult
from domain.models.events import EarlyFeedbackGenerated
from domain.models.pattern import EarlyFeedback
from domain.ports import (
    ICycleRepository,
    IEventPublisher,
    ILogRepository,
    IPatternRepository,
)
from application.use_cases.log_daily_entry import INSIGHT_UNLOCK_THRESHOLD


# ---------------------------------------------------------------------------
# GetHomeState
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GetHomeStateCommand(Command):
    user_id: UUID
    today: date


@dataclass(frozen=True)
class HomeState(Result):
    """
    Everything the Home screen needs to render.

    Fields:
        has_logged_today:     Whether the user has already logged today.
        log_count:            Total logs submitted.
        current_cycle_day:    Inferred cycle day for today. None if no baseline.
        current_phase:        Inferred cycle phase for today. None if no baseline.
        phase_is_reliable:    False if the baseline is irregular with no length.
        streak:               Consecutive days logged ending today.
        logs_until_unlock:    How many more logs until the Insights screen unlocks.
        is_insights_unlocked: True if log_count >= threshold and a pattern exists.
        early_feedback:       The most recent reinforcement message, if any.
    """
    has_logged_today: bool
    log_count: int
    current_cycle_day: Optional[int]
    current_phase: Optional[str]       # phase display name, not enum
    phase_is_reliable: bool
    streak: int
    logs_until_unlock: int
    is_insights_unlocked: bool
    early_feedback: Optional[str]      # message string, not EarlyFeedback model


class GetHomeState:

    def __init__(
        self,
        log_repo: ILogRepository,
        cycle_repo: ICycleRepository,
        pattern_repo: IPatternRepository,
        phase_calculator: Optional[PhaseCalculator] = None,
    ) -> None:
        self._log_repo = log_repo
        self._cycle_repo = cycle_repo
        self._pattern_repo = pattern_repo
        self._phase_calculator = phase_calculator or PhaseCalculator()

    def execute(self, command: GetHomeStateCommand) -> HomeState:
        has_logged_today = self._log_repo.has_log_for_date(
            command.user_id, command.today
        )

        log_count = self._log_repo.count_logs_for_user(command.user_id)

        # Phase inference
        baseline = self._cycle_repo.get_by_user_id(command.user_id)
        current_cycle_day: Optional[int] = None
        current_phase: Optional[str] = None
        phase_is_reliable = False

        if baseline is not None:
            phase_result = self._phase_calculator.calculate(baseline, command.today)
            current_cycle_day = phase_result.cycle_day
            current_phase = phase_result.phase.display_name
            phase_is_reliable = phase_result.is_reliable

        # Streak calculation
        streak = self._calculate_streak(command.user_id, command.today)

        # Insights unlock state
        has_pattern = self._pattern_repo.get_latest_pattern(command.user_id) is not None
        is_insights_unlocked = log_count >= INSIGHT_UNLOCK_THRESHOLD and has_pattern
        logs_until_unlock = max(0, INSIGHT_UNLOCK_THRESHOLD - log_count)

        # Early feedback
        feedback = self._pattern_repo.get_latest_feedback(command.user_id)
        early_feedback_message = feedback.message if feedback is not None else None

        return HomeState(
            has_logged_today=has_logged_today,
            log_count=log_count,
            current_cycle_day=current_cycle_day,
            current_phase=current_phase,
            phase_is_reliable=phase_is_reliable,
            streak=streak,
            logs_until_unlock=logs_until_unlock,
            is_insights_unlocked=is_insights_unlocked,
            early_feedback=early_feedback_message,
        )

    def _calculate_streak(self, user_id: UUID, today: date) -> int:
        """
        Count consecutive days logged ending on today.

        Walks backwards from today. Stops at the first missing day.
        A streak of 0 means today has no log yet.
        """
        from datetime import timedelta

        streak = 0
        current = today

        while True:
            if not self._log_repo.has_log_for_date(user_id, current):
                break
            streak += 1
            current = current - timedelta(days=1)

        return streak


# ---------------------------------------------------------------------------
# GenerateEarlyFeedback
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GenerateEarlyFeedbackCommand(Command):
    user_id: UUID


@dataclass(frozen=True)
class GenerateEarlyFeedbackResult(Result):
    feedback: Optional[EarlyFeedback]
    was_generated: bool
    """
    False if not enough logs exist or no clear observation was found.
    Not an error — this is expected before day 7.
    """


class GenerateEarlyFeedback:
    """
    Generates an early feedback sentence for the Home screen.

    Called every 5–7 days during the day 7–30 window.
    After the Insights screen unlocks, early feedback is no longer needed.

    Does not raise. Returns was_generated=False if feedback cannot
    be produced (too few logs, no observable pattern).
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

    def execute(self, command: GenerateEarlyFeedbackCommand) -> GenerateEarlyFeedbackResult:
        logs = self._log_repo.get_logs_for_user(command.user_id)

        if len(logs) < MIN_LOGS_FOR_FEEDBACK:
            return GenerateEarlyFeedbackResult(
                feedback=None,
                was_generated=False,
            )

        sorted_logs = sorted(logs, key=lambda l: l.logged_date)
        feedback = self._engine.generate_early_feedback(sorted_logs)

        if feedback is None:
            return GenerateEarlyFeedbackResult(
                feedback=None,
                was_generated=False,
            )

        self._pattern_repo.save_feedback(feedback)

        self._event_publisher.publish(EarlyFeedbackGenerated(
            user_id=command.user_id,
            occurred_at=datetime.utcnow(),
            trigger_phase=feedback.trigger_phase,
            log_count=feedback.log_count,
        ))

        return GenerateEarlyFeedbackResult(
            feedback=feedback,
            was_generated=True,
        )
