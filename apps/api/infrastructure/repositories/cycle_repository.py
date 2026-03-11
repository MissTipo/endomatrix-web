"""
infrastructure.repositories.cycle_repository

PostgresCycleRepository — concrete IICycleRepository backed by PostgreSQL.

One row per user. save() is an upsert — it replaces the existing row
if one exists, or inserts a new one. This matches the domain invariant
that each user has at most one active baseline.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from domain.models.cycle import CycleBaseline
from domain.ports import ICycleRepository
from infrastructure.orm.tables import cycle_baselines


class PostgresCycleRepository(ICycleRepository):

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, baseline: CycleBaseline) -> None:
        """
        Upsert a cycle baseline.

        Uses PostgreSQL's INSERT ... ON CONFLICT DO UPDATE to atomically
        replace the existing row without needing a separate SELECT first.
        """
        stmt = (
            pg_insert(cycle_baselines)
            .values(
                user_id=baseline.user_id,
                last_period_start=baseline.last_period_start.isoformat(),
                average_cycle_length=baseline.average_cycle_length,
                is_irregular=baseline.is_irregular,
                updated_at=baseline.updated_at,
            )
            .on_conflict_do_update(
                index_elements=["user_id"],
                set_={
                    "last_period_start": baseline.last_period_start.isoformat(),
                    "average_cycle_length": baseline.average_cycle_length,
                    "is_irregular": baseline.is_irregular,
                    "updated_at": baseline.updated_at,
                },
            )
        )
        self._session.execute(stmt)

    def get_by_user_id(self, user_id: UUID) -> Optional[CycleBaseline]:
        row = self._session.execute(
            select(cycle_baselines).where(cycle_baselines.c.user_id == user_id)
        ).mappings().one_or_none()
        return self._row_to_domain(row) if row else None

    def exists(self, user_id: UUID) -> bool:
        return self.get_by_user_id(user_id) is not None

    @staticmethod
    def _row_to_domain(row: dict) -> CycleBaseline:
        return CycleBaseline(
            user_id=row["user_id"],
            last_period_start=date.fromisoformat(row["last_period_start"]),
            average_cycle_length=row["average_cycle_length"],
            is_irregular=row["is_irregular"],
            updated_at=row["updated_at"],
        )
