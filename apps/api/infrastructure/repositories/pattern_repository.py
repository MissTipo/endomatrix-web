"""
infrastructure.repositories.pattern_repository

PostgresPatternRepository — concrete IPatternRepository backed by PostgreSQL.

PatternResult rows are append-only. save_pattern() always inserts, never
updates. Old results are kept so the user can see how their pattern has
changed over time.

The nested fields (symptom_clusters, phase_patterns, prediction) are stored
as JSONB in the `payload` column. The serializers module handles the
round-trip translation between JSONB dicts and domain objects.

EarlyFeedback rows are also append-only. get_latest_feedback() returns the
one with the most recent generated_at.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from domain.models.cycle import CyclePhase
from domain.models.pattern import (
    EarlyFeedback,
    EscalationSpeed,
    PatternResult,
    SeverityTrend,
)
from domain.ports import IPatternRepository
from infrastructure.orm.serializers import build_pattern_payload, unpack_pattern_payload
from infrastructure.orm.tables import early_feedback as early_feedback_table
from infrastructure.orm.tables import pattern_results


class PostgresPatternRepository(IPatternRepository):

    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # PatternResult
    # ------------------------------------------------------------------

    def save_pattern(self, result: PatternResult) -> None:
        payload = build_pattern_payload(
            symptom_clusters=result.symptom_clusters,
            phase_patterns=result.phase_patterns,
            prediction=result.prediction,
        )

        self._session.execute(
            pattern_results.insert().values(
                id=result.id,
                user_id=result.user_id,
                generated_at=result.generated_at,
                cycles_analyzed=result.cycles_analyzed,
                total_logs=result.total_logs,
                onset_range_start=result.symptom_onset_range[0],
                onset_range_end=result.symptom_onset_range[1],
                escalation_speed=result.escalation_speed.value,
                severity_trend=result.severity_trend.value,
                payload=payload,
            )
        )

    def get_latest_pattern(self, user_id: UUID) -> Optional[PatternResult]:
        row = self._session.execute(
            select(pattern_results)
            .where(pattern_results.c.user_id == user_id)
            .order_by(pattern_results.c.generated_at.desc())
            .limit(1)
        ).mappings().one_or_none()
        return self._row_to_domain(row) if row else None

    def get_pattern_by_id(self, pattern_id: UUID) -> Optional[PatternResult]:
        row = self._session.execute(
            select(pattern_results).where(pattern_results.c.id == pattern_id)
        ).mappings().one_or_none()
        return self._row_to_domain(row) if row else None

    def get_all_patterns(self, user_id: UUID) -> list[PatternResult]:
        rows = self._session.execute(
            select(pattern_results)
            .where(pattern_results.c.user_id == user_id)
            .order_by(pattern_results.c.generated_at.desc())
        ).mappings().all()
        return [self._row_to_domain(r) for r in rows]

    def count_patterns(self, user_id: UUID) -> int:
        from sqlalchemy import func
        result = self._session.execute(
            select(func.count())
            .select_from(pattern_results)
            .where(pattern_results.c.user_id == user_id)
        ).scalar()
        return result or 0

    # ------------------------------------------------------------------
    # EarlyFeedback
    # ------------------------------------------------------------------

    def save_feedback(self, feedback: EarlyFeedback) -> None:
        self._session.execute(
            early_feedback_table.insert().values(
                id=uuid4(),
                user_id=feedback.user_id,
                message=feedback.message,
                generated_at=feedback.generated_at,
                log_count=feedback.log_count,
                trigger_phase=feedback.trigger_phase.value if feedback.trigger_phase else None,
            )
        )

    def get_latest_feedback(self, user_id: UUID) -> Optional[EarlyFeedback]:
        row = self._session.execute(
            select(early_feedback_table)
            .where(early_feedback_table.c.user_id == user_id)
            .order_by(early_feedback_table.c.generated_at.desc())
            .limit(1)
        ).mappings().one_or_none()
        return self._feedback_row_to_domain(row) if row else None

    # ------------------------------------------------------------------
    # Translation
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_domain(row: dict) -> PatternResult:
        clusters, phase_patterns, prediction = unpack_pattern_payload(row["payload"])
        return PatternResult(
            id=row["id"],
            user_id=row["user_id"],
            generated_at=row["generated_at"],
            cycles_analyzed=row["cycles_analyzed"],
            total_logs=row["total_logs"],
            symptom_onset_range=(row["onset_range_start"], row["onset_range_end"]),
            escalation_speed=EscalationSpeed(row["escalation_speed"]),
            severity_trend=SeverityTrend(row["severity_trend"]),
            symptom_clusters=clusters,
            phase_patterns=phase_patterns,
            prediction=prediction,
        )

    @staticmethod
    def _feedback_row_to_domain(row: dict) -> EarlyFeedback:
        trigger = row["trigger_phase"]
        return EarlyFeedback(
            user_id=row["user_id"],
            message=row["message"],
            generated_at=row["generated_at"],
            log_count=row["log_count"],
            trigger_phase=CyclePhase(trigger) if trigger else None,
        )
