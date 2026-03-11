"""
use_cases.log_daily_entry

LogDailyEntry — called when the user taps "Log today" on the Daily Log screen.

This is the most important use case in the system. Everything else —
patterns, insights, feedback — depends on this being correct.

What it does:
1. Loads the user's cycle baseline
2. Calculates the cycle day and phase for today using PhaseCalculator
3. Constructs a DailyLog domain model
4. Saves it via ILogRepository (handles supersession transparently)
5. Publishes LogCreated (or LogSuperseded + LogCreated if replacing)
6. Returns the saved log and whether the 30-day threshold was just crossed

The 30-day threshold check is returned so the caller (presentation layer)
can decide whether to trigger pattern generation. The use case itself
does not generate patterns — that is GeneratePattern's responsibility.
Keeping these separate means pattern generation can be triggered
independently (e.g. on a schedule or by a background job) without
coupling it to the log submission flow.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional
from uuid import UUID, uuid4

from application.base import Command, Result
from domain.engine.phase_calculator import PhaseCalculator
from domain.models.cycle import CyclePhase, Score
from domain.models.daily_log import DailyLog
from domain.models.events import LogCreated, LogSuperseded
from domain.models.symptom import Symptom
from domain.ports import ICycleRepository, IEventPublisher, ILogRepository

# The number of logs after which the Insights screen unlocks.
INSIGHT_UNLOCK_THRESHOLD = 30


@dataclass(frozen=True)
class LogDailyEntryCommand(Command):
    user_id: UUID
    logged_date: date
    pain_level: int           # 0–10, validated by Score on construction
    energy_level: int         # 0–10
    dominant_symptom: Symptom
    mood_level: Optional[int] = None   # 0–10, MVP field
    note: Optional[str] = None         # free text, MVP field


@dataclass(frozen=True)
class LogDailyEntryResult(Result):
    log: DailyLog
    log_count: int
    insight_threshold_crossed: bool
    """
    True if this log brought the total to exactly INSIGHT_UNLOCK_THRESHOLD.
    The presentation layer should use this to trigger GeneratePattern
    and show the Insights unlock screen.
    """
    was_superseded: bool
    """
    True if a previous log existed for this date and was superseded.
    Useful for the presentation layer to show a "log updated" confirmation
    rather than a "log saved" confirmation.
    """


class LogDailyEntry:
    """
    Submits a daily log for a user.

    Raises:
        ValueError: if no cycle baseline exists for this user.
                    The user must complete onboarding before logging.
        ValueError: if the logged_date is in the future.
                    This is enforced by DailyLog itself but surfaced
                    here with a clearer message.
    """

    def __init__(
        self,
        log_repo: ILogRepository,
        cycle_repo: ICycleRepository,
        event_publisher: IEventPublisher,
        phase_calculator: Optional[PhaseCalculator] = None,
    ) -> None:
        self._log_repo = log_repo
        self._cycle_repo = cycle_repo
        self._event_publisher = event_publisher
        self._phase_calculator = phase_calculator or PhaseCalculator()

    def execute(self, command: LogDailyEntryCommand) -> LogDailyEntryResult:
        # 1. Load cycle baseline — required before any log can be created
        baseline = self._cycle_repo.get_by_user_id(command.user_id)
        if baseline is None:
            raise ValueError(
                f"No cycle baseline found for user {command.user_id}. "
                "Complete onboarding before submitting a daily log."
            )

        # 2. Infer cycle day and phase
        phase_result = self._phase_calculator.calculate(baseline, command.logged_date)

        # 3. Check if a log already exists for this date
        existing_log = self._log_repo.get_by_date(command.user_id, command.logged_date)
        was_superseded = existing_log is not None

        # 4. Construct the domain model
        log = DailyLog(
            id=uuid4(),
            user_id=command.user_id,
            logged_date=command.logged_date,
            pain_level=Score(command.pain_level),
            energy_level=Score(command.energy_level),
            dominant_symptom=command.dominant_symptom,
            cycle_day=phase_result.cycle_day,
            cycle_phase=phase_result.phase,
            created_at=datetime.utcnow(),
            mood_level=Score(command.mood_level) if command.mood_level is not None else None,
            note=command.note,
        )

        # 5. Save — repository handles supersession internally
        self._log_repo.save(log)

        # 6. Publish events
        events = []

        if was_superseded and existing_log is not None:
            events.append(LogSuperseded(
                user_id=command.user_id,
                occurred_at=datetime.utcnow(),
                original_log_id=existing_log.id,
                new_log_id=log.id,
                logged_date=command.logged_date.isoformat(),
            ))

        events.append(LogCreated(
            user_id=command.user_id,
            occurred_at=datetime.utcnow(),
            log_id=log.id,
            logged_date=command.logged_date.isoformat(),
            cycle_phase=log.cycle_phase,
            pain_level=log.pain_level.value,
            energy_level=log.energy_level.value,
        ))

        self._event_publisher.publish_all(events)

        # 7. Check threshold
        log_count = self._log_repo.count_logs_for_user(command.user_id)
        insight_threshold_crossed = log_count == INSIGHT_UNLOCK_THRESHOLD

        return LogDailyEntryResult(
            log=log,
            log_count=log_count,
            insight_threshold_crossed=insight_threshold_crossed,
            was_superseded=was_superseded,
        )
