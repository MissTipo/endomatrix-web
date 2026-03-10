"""
In-memory implementations of all domain ports.

These are used in:
- Unit tests for the application layer and engine
- Local development without a running database
- Contract tests that verify any implementation satisfies the port

They are intentionally simple. No persistence, no concurrency,
no optimisation. A plain dict is enough.

Location note: fakes live in tests/ not in the production code.
They are a test concern, not a production concern.
"""

from datetime import date
from typing import Optional
from uuid import UUID

from domain.models.cycle import CycleBaseline, CyclePhase
from domain.models.daily_log import DailyLog
from domain.models.events import DomainEvent
from domain.models.pattern import EarlyFeedback, PatternResult
from domain.ports import (
    ICycleRepository,
    IEventPublisher,
    ILogRepository,
    IPatternRepository,
)


class InMemoryLogRepository(ILogRepository):
    """
    In-memory implementation of ILogRepository.
    Stores logs in a dict keyed by log ID.
    Superseded logs are tracked separately.
    """

    def __init__(self) -> None:
        self._logs: dict[UUID, DailyLog] = {}
        self._superseded: set[UUID] = set()

    def save(self, log: DailyLog) -> None:
        # Mark any existing log for this user+date as superseded
        existing = self.get_by_date(log.user_id, log.logged_date)
        if existing is not None:
            self._superseded.add(existing.id)
        self._logs[log.id] = log

    def get_by_id(self, log_id: UUID) -> Optional[DailyLog]:
        log = self._logs.get(log_id)
        if log is None or log.id in self._superseded:
            return None
        return log

    def get_by_date(self, user_id: UUID, logged_date: date) -> Optional[DailyLog]:
        for log in self._active_logs():
            if log.user_id == user_id and log.logged_date == logged_date:
                return log
        return None

    def get_logs_for_user(
        self,
        user_id: UUID,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> list[DailyLog]:
        logs = sorted(
            [l for l in self._active_logs() if l.user_id == user_id],
            key=lambda l: l.logged_date,
            reverse=True,
        )
        if offset:
            logs = logs[offset:]
        if limit is not None:
            logs = logs[:limit]
        return logs

    def get_logs_in_range(
        self,
        user_id: UUID,
        start_date: date,
        end_date: date,
    ) -> list[DailyLog]:
        return sorted(
            [
                l for l in self._active_logs()
                if l.user_id == user_id
                and start_date <= l.logged_date <= end_date
            ],
            key=lambda l: l.logged_date,
        )

    def get_logs_by_phase(
        self,
        user_id: UUID,
        phase: CyclePhase,
    ) -> list[DailyLog]:
        return [
            l for l in self._active_logs()
            if l.user_id == user_id and l.cycle_phase == phase
        ]

    def count_logs_for_user(self, user_id: UUID) -> int:
        return sum(1 for l in self._active_logs() if l.user_id == user_id)

    def has_log_for_date(self, user_id: UUID, logged_date: date) -> bool:
        return self.get_by_date(user_id, logged_date) is not None

    def get_most_recent_log(self, user_id: UUID) -> Optional[DailyLog]:
        logs = self.get_logs_for_user(user_id, limit=1)
        return logs[0] if logs else None

    def _active_logs(self):
        return [l for l in self._logs.values() if l.id not in self._superseded]


class InMemoryCycleRepository(ICycleRepository):

    def __init__(self) -> None:
        self._baselines: dict[UUID, CycleBaseline] = {}

    def save(self, baseline: CycleBaseline) -> None:
        self._baselines[baseline.user_id] = baseline

    def get_by_user_id(self, user_id: UUID) -> Optional[CycleBaseline]:
        return self._baselines.get(user_id)

    def exists(self, user_id: UUID) -> bool:
        return user_id in self._baselines


class InMemoryPatternRepository(IPatternRepository):

    def __init__(self) -> None:
        self._patterns: dict[UUID, PatternResult] = {}
        self._feedback: dict[UUID, list[EarlyFeedback]] = {}

    def save_pattern(self, result: PatternResult) -> None:
        self._patterns[result.id] = result

    def get_latest_pattern(self, user_id: UUID) -> Optional[PatternResult]:
        user_patterns = self.get_all_patterns(user_id)
        return user_patterns[0] if user_patterns else None

    def get_pattern_by_id(self, pattern_id: UUID) -> Optional[PatternResult]:
        return self._patterns.get(pattern_id)

    def get_all_patterns(self, user_id: UUID) -> list[PatternResult]:
        return sorted(
            [p for p in self._patterns.values() if p.user_id == user_id],
            key=lambda p: p.generated_at,
            reverse=True,
        )

    def count_patterns(self, user_id: UUID) -> int:
        return sum(1 for p in self._patterns.values() if p.user_id == user_id)

    def save_feedback(self, feedback: EarlyFeedback) -> None:
        self._feedback.setdefault(feedback.user_id, []).append(feedback)

    def get_latest_feedback(self, user_id: UUID) -> Optional[EarlyFeedback]:
        entries = self._feedback.get(user_id, [])
        if not entries:
            return None
        return max(entries, key=lambda f: f.generated_at)


class InMemoryEventPublisher(IEventPublisher):
    """
    Captures published events for inspection in tests.

    Usage:
        publisher = InMemoryEventPublisher()
        # ... run use case ...
        assert len(publisher.events) == 1
        assert isinstance(publisher.events[0], LogCreated)
    """

    def __init__(self) -> None:
        self.events: list[DomainEvent] = []

    def publish(self, event: DomainEvent) -> None:
        self.events.append(event)

    def publish_all(self, events: list[DomainEvent]) -> None:
        self.events.extend(events)

    def clear(self) -> None:
        self.events.clear()

    def of_type(self, event_type: type) -> list[DomainEvent]:
        """Convenience: return only events of a given type."""
        return [e for e in self.events if isinstance(e, event_type)]
