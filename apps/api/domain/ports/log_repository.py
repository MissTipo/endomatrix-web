"""
ILogRepository

The persistence interface for DailyLog records.

This is what the domain and application layers depend on.
The infrastructure layer provides the concrete implementation
(PostgresLogRepository). Tests provide an in-memory fake.

The domain never imports SQLAlchemy, never opens a connection,
never writes a query. It only calls methods defined here.

Design rules:
- Every method is abstract. No default implementations.
- Methods are named for what they mean to the domain,
  not how they work in a database. get_logs_for_user,
  not SELECT * FROM daily_logs WHERE user_id = ...
- Return types are domain models, not ORM objects.
  The infrastructure layer handles the translation.
- Methods that look up a single record return Optional.
  None means "not found" — it is not an error.
- Methods that return collections return list, never None.
  An empty list means "nothing found."
"""

from abc import ABC, abstractmethod
from datetime import date
from typing import Optional
from uuid import UUID

from domain.models.daily_log import DailyLog
from domain.models.cycle import CyclePhase


class ILogRepository(ABC):

    @abstractmethod
    def save(self, log: DailyLog) -> None:
        """
        Persist a new DailyLog.

        If a log already exists for (user_id, logged_date), the
        infrastructure layer marks the existing one as superseded
        and saves the new one. This method does not raise on
        duplicate dates — supersession is handled transparently.
        """
        ...

    @abstractmethod
    def get_by_id(self, log_id: UUID) -> Optional[DailyLog]:
        """
        Retrieve a single log by its ID.
        Returns None if no log with that ID exists.
        """
        ...

    @abstractmethod
    def get_by_date(self, user_id: UUID, logged_date: date) -> Optional[DailyLog]:
        """
        Retrieve the active log for a user on a specific calendar date.
        Returns None if no log exists for that date.
        Only returns the active log — superseded logs are excluded.
        """
        ...

    @abstractmethod
    def get_logs_for_user(
        self,
        user_id: UUID,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> list[DailyLog]:
        """
        Retrieve all active logs for a user, ordered by logged_date descending.

        limit: maximum number of logs to return. None means no limit.
        offset: number of logs to skip (for pagination).

        Only returns active logs. Superseded logs are excluded.
        """
        ...

    @abstractmethod
    def get_logs_in_range(
        self,
        user_id: UUID,
        start_date: date,
        end_date: date,
    ) -> list[DailyLog]:
        """
        Retrieve all active logs for a user within a date range, inclusive.
        Ordered by logged_date ascending.

        Used by the pattern engine to analyze a specific time window.
        """
        ...

    @abstractmethod
    def get_logs_by_phase(
        self,
        user_id: UUID,
        phase: CyclePhase,
    ) -> list[DailyLog]:
        """
        Retrieve all active logs for a user where the inferred cycle
        phase matches the given phase.

        Used by the pattern engine to build per-phase breakdowns.
        """
        ...

    @abstractmethod
    def count_logs_for_user(self, user_id: UUID) -> int:
        """
        Return the total number of active logs for a user.

        Used to determine whether the 30-day insight threshold
        has been reached without loading all logs into memory.
        """
        ...

    @abstractmethod
    def has_log_for_date(self, user_id: UUID, logged_date: date) -> bool:
        """
        Return True if an active log exists for this user on this date.

        Used by the Home screen to show the logged vs unlogged state
        without loading the full log record.
        """
        ...

    @abstractmethod
    def get_most_recent_log(self, user_id: UUID) -> Optional[DailyLog]:
        """
        Return the most recently logged entry for a user.
        Returns None if the user has no logs at all.
        """
        ...
