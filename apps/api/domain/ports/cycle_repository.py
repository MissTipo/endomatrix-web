"""
ICycleRepository

The persistence interface for CycleBaseline records.

One baseline per user. It is created at onboarding and updated
when the user edits their cycle info in Settings.

The baseline is the anchor for all phase inference. Without it,
the PhaseCalculator cannot assign cycle days or phases to logs.
"""

from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from domain.models.cycle import CycleBaseline


class ICycleRepository(ABC):

    @abstractmethod
    def save(self, baseline: CycleBaseline) -> None:
        """
        Persist a CycleBaseline for a user.

        If a baseline already exists for this user_id, it is
        replaced. There is always at most one active baseline
        per user.
        """
        ...

    @abstractmethod
    def get_by_user_id(self, user_id: UUID) -> Optional[CycleBaseline]:
        """
        Retrieve the cycle baseline for a user.
        Returns None if the user has not yet completed onboarding
        or has not provided cycle information.
        """
        ...

    @abstractmethod
    def exists(self, user_id: UUID) -> bool:
        """
        Return True if a cycle baseline exists for this user.

        Used to determine whether a user has completed the
        onboarding cycle step without loading the full record.
        """
        ...
