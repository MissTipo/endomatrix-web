"""
infrastructure.repositories.log_repository

PostgresLogRepository — the real ILogRepository backed by PostgreSQL.

Supersession logic:
    When save() is called for a (user_id, logged_date) pair that already
    has an active log, the existing row's is_active flag is set to False
    before the new row is inserted. This preserves the audit trail while
    keeping the "one active log per date" invariant the domain requires.

    The DB enforces this with a partial unique index on (user_id, logged_date)
    WHERE is_active = true. This allows unlimited superseded (inactive) rows
    for the same user/date while still blocking two active rows. The application
    layer and this repository both enforce it — defence in depth.

All methods return domain models, never SQLAlchemy Row objects.
The translation happens in _row_to_domain().
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from domain.models.cycle import CyclePhase, Score
from domain.models.daily_log import DailyLog
from domain.models.symptom import Symptom
from domain.ports import ILogRepository
from infrastructure.orm.tables import daily_logs


class PostgresLogRepository(ILogRepository):

    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def save(self, log: DailyLog) -> None:
        # Supersede any existing active log for this user+date
        self._session.execute(
            update(daily_logs)
            .where(
                daily_logs.c.user_id == log.user_id,
                daily_logs.c.logged_date == log.logged_date.isoformat(),
                daily_logs.c.is_active == True,  # noqa: E712
            )
            .values(is_active=False)
        )

        self._session.execute(
            daily_logs.insert().values(
                id=log.id,
                user_id=log.user_id,
                logged_date=log.logged_date.isoformat(),
                pain_level=log.pain_level.value,
                energy_level=log.energy_level.value,
                mood_level=log.mood_level.value if log.mood_level is not None else None,
                dominant_symptom=log.dominant_symptom.value,
                note=log.note,
                cycle_day=log.cycle_day,
                cycle_phase=log.cycle_phase.value,
                created_at=log.created_at,
                is_active=True,
            )
        )

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get_by_id(self, log_id: UUID) -> Optional[DailyLog]:
        row = self._session.execute(
            select(daily_logs).where(
                daily_logs.c.id == log_id,
                daily_logs.c.is_active == True,  # noqa: E712
            )
        ).mappings().one_or_none()
        return self._row_to_domain(row) if row else None

    def get_by_date(self, user_id: UUID, logged_date: date) -> Optional[DailyLog]:
        row = self._session.execute(
            select(daily_logs).where(
                daily_logs.c.user_id == user_id,
                daily_logs.c.logged_date == logged_date.isoformat(),
                daily_logs.c.is_active == True,  # noqa: E712
            )
        ).mappings().one_or_none()
        return self._row_to_domain(row) if row else None

    def get_logs_for_user(
        self,
        user_id: UUID,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> list[DailyLog]:
        query = (
            select(daily_logs)
            .where(
                daily_logs.c.user_id == user_id,
                daily_logs.c.is_active == True,  # noqa: E712
            )
            .order_by(daily_logs.c.logged_date.desc())
            .offset(offset)
        )
        if limit is not None:
            query = query.limit(limit)

        rows = self._session.execute(query).mappings().all()
        return [self._row_to_domain(r) for r in rows]

    def get_logs_in_range(
        self,
        user_id: UUID,
        start_date: date,
        end_date: date,
    ) -> list[DailyLog]:
        rows = self._session.execute(
            select(daily_logs)
            .where(
                daily_logs.c.user_id == user_id,
                daily_logs.c.is_active == True,  # noqa: E712
                daily_logs.c.logged_date >= start_date.isoformat(),
                daily_logs.c.logged_date <= end_date.isoformat(),
            )
            .order_by(daily_logs.c.logged_date.asc())
        ).mappings().all()
        return [self._row_to_domain(r) for r in rows]

    def get_logs_by_phase(
        self,
        user_id: UUID,
        phase: CyclePhase,
    ) -> list[DailyLog]:
        rows = self._session.execute(
            select(daily_logs).where(
                daily_logs.c.user_id == user_id,
                daily_logs.c.is_active == True,  # noqa: E712
                daily_logs.c.cycle_phase == phase.value,
            )
        ).mappings().all()
        return [self._row_to_domain(r) for r in rows]

    def count_logs_for_user(self, user_id: UUID) -> int:
        from sqlalchemy import func
        result = self._session.execute(
            select(func.count())
            .select_from(daily_logs)
            .where(
                daily_logs.c.user_id == user_id,
                daily_logs.c.is_active == True,  # noqa: E712
            )
        ).scalar()
        return result or 0

    def has_log_for_date(self, user_id: UUID, logged_date: date) -> bool:
        return self.get_by_date(user_id, logged_date) is not None

    def get_most_recent_log(self, user_id: UUID) -> Optional[DailyLog]:
        logs = self.get_logs_for_user(user_id, limit=1)
        return logs[0] if logs else None

    # ------------------------------------------------------------------
    # Translation
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_domain(row: dict) -> DailyLog:
        mood = row["mood_level"]
        return DailyLog(
            id=row["id"],
            user_id=row["user_id"],
            logged_date=date.fromisoformat(row["logged_date"]),
            pain_level=Score(row["pain_level"]),
            energy_level=Score(row["energy_level"]),
            mood_level=Score(mood) if mood is not None else None,
            dominant_symptom=Symptom(row["dominant_symptom"]),
            note=row["note"],
            cycle_day=row["cycle_day"],
            cycle_phase=CyclePhase(row["cycle_phase"]),
            created_at=row["created_at"],
        )
