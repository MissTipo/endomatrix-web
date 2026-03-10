"""
IPatternRepository

The persistence interface for PatternResult and EarlyFeedback records.

PatternResults are versioned — each analysis run produces a new record.
They are never updated in place. Old results are retained so the user
can see how their pattern has changed over time.

EarlyFeedback records are lightweight and short-lived. They are stored
so the Home screen can retrieve the most recent one without regenerating
it on every request.
"""

from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from domain.models.pattern import EarlyFeedback, PatternResult


class IPatternRepository(ABC):

    # ------------------------------------------------------------------
    # PatternResult
    # ------------------------------------------------------------------

    @abstractmethod
    def save_pattern(self, result: PatternResult) -> None:
        """
        Persist a new PatternResult.

        Never updates an existing result. Each analysis run
        produces a new record alongside the previous ones.
        """
        ...

    @abstractmethod
    def get_latest_pattern(self, user_id: UUID) -> Optional[PatternResult]:
        """
        Retrieve the most recently generated PatternResult for a user.
        Returns None if no pattern has been generated yet.

        This is what the Insights screen renders.
        """
        ...

    @abstractmethod
    def get_pattern_by_id(self, pattern_id: UUID) -> Optional[PatternResult]:
        """
        Retrieve a specific PatternResult by its ID.
        Returns None if no result with that ID exists.
        """
        ...

    @abstractmethod
    def get_all_patterns(self, user_id: UUID) -> list[PatternResult]:
        """
        Retrieve all PatternResults for a user, ordered by
        generated_at descending (most recent first).

        Used for the cycle comparison feature in the MVP.
        """
        ...

    @abstractmethod
    def count_patterns(self, user_id: UUID) -> int:
        """
        Return the total number of PatternResults generated for a user.

        Used to determine whether this is the user's first pattern
        (the 30-day unlock moment) without loading all records.
        """
        ...

    # ------------------------------------------------------------------
    # EarlyFeedback
    # ------------------------------------------------------------------

    @abstractmethod
    def save_feedback(self, feedback: EarlyFeedback) -> None:
        """
        Persist an EarlyFeedback record.

        Multiple feedback records can exist per user — one is
        generated every 5–7 days during the day 7–30 window.
        """
        ...

    @abstractmethod
    def get_latest_feedback(self, user_id: UUID) -> Optional[EarlyFeedback]:
        """
        Retrieve the most recently generated EarlyFeedback for a user.
        Returns None if no feedback has been generated yet.

        This is what the Home screen renders in the feedback card.
        """
        ...
