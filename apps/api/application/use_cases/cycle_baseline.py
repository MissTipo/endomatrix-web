"""
use_cases.cycle_baseline

SetCycleBaseline  — called once during onboarding
UpdateCycleBaseline — called from Settings when user edits cycle info

Both use cases write to ICycleRepository and publish a domain event.
The difference is which event they emit and the validation context:
- SetCycleBaseline rejects if a baseline already exists for this user
- UpdateCycleBaseline rejects if no baseline exists yet
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from application.base import Command, Result
from domain.models.cycle import CycleBaseline
from domain.models.events import CycleBaselineSet, CycleBaselineUpdated
from domain.ports import ICycleRepository, IEventPublisher


# ---------------------------------------------------------------------------
# SetCycleBaseline
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SetCycleBaselineCommand(Command):
    user_id: UUID
    last_period_start: date
    average_cycle_length: Optional[int]
    is_irregular: bool


@dataclass(frozen=True)
class SetCycleBaselineResult(Result):
    baseline: CycleBaseline


class SetCycleBaseline:
    """
    Creates the initial cycle baseline for a user during onboarding.

    Raises:
        ValueError: if a baseline already exists for this user.
                    Onboarding should only run once. Use UpdateCycleBaseline
                    for subsequent changes.
    """

    def __init__(
        self,
        cycle_repo: ICycleRepository,
        event_publisher: IEventPublisher,
    ) -> None:
        self._cycle_repo = cycle_repo
        self._event_publisher = event_publisher

    def execute(self, command: SetCycleBaselineCommand) -> SetCycleBaselineResult:
        if self._cycle_repo.exists(command.user_id):
            raise ValueError(
                f"Cycle baseline already exists for user {command.user_id}. "
                "Use UpdateCycleBaseline to change cycle information."
            )

        baseline = CycleBaseline(
            user_id=command.user_id,
            last_period_start=command.last_period_start,
            average_cycle_length=command.average_cycle_length,
            is_irregular=command.is_irregular,
            updated_at=datetime.utcnow(),
        )

        self._cycle_repo.save(baseline)

        self._event_publisher.publish(CycleBaselineSet(
            user_id=command.user_id,
            occurred_at=datetime.utcnow(),
            last_period_start=baseline.last_period_start.isoformat(),
            average_cycle_length=baseline.average_cycle_length,
            is_irregular=baseline.is_irregular,
        ))

        return SetCycleBaselineResult(baseline=baseline)


# ---------------------------------------------------------------------------
# UpdateCycleBaseline
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class UpdateCycleBaselineCommand(Command):
    user_id: UUID
    last_period_start: date
    average_cycle_length: Optional[int]
    is_irregular: bool


@dataclass(frozen=True)
class UpdateCycleBaselineResult(Result):
    baseline: CycleBaseline


class UpdateCycleBaseline:
    """
    Updates an existing cycle baseline from the Settings screen.

    Raises:
        ValueError: if no baseline exists for this user yet.
                    The user must complete onboarding first.
    """

    def __init__(
        self,
        cycle_repo: ICycleRepository,
        event_publisher: IEventPublisher,
    ) -> None:
        self._cycle_repo = cycle_repo
        self._event_publisher = event_publisher

    def execute(self, command: UpdateCycleBaselineCommand) -> UpdateCycleBaselineResult:
        existing = self._cycle_repo.get_by_user_id(command.user_id)
        if existing is None:
            raise ValueError(
                f"No cycle baseline found for user {command.user_id}. "
                "Use SetCycleBaseline during onboarding first."
            )

        updated = CycleBaseline(
            user_id=command.user_id,
            last_period_start=command.last_period_start,
            average_cycle_length=command.average_cycle_length,
            is_irregular=command.is_irregular,
            updated_at=datetime.utcnow(),
        )

        self._cycle_repo.save(updated)

        self._event_publisher.publish(CycleBaselineUpdated(
            user_id=command.user_id,
            occurred_at=datetime.utcnow(),
            previous_last_period_start=existing.last_period_start.isoformat(),
            new_last_period_start=updated.last_period_start.isoformat(),
            previous_cycle_length=existing.average_cycle_length,
            new_cycle_length=updated.average_cycle_length,
        ))

        return UpdateCycleBaselineResult(baseline=updated)
