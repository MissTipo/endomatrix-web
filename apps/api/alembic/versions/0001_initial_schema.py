"""
0001_initial_schema

Creates the initial EndoMatrix schema:
    - daily_logs
    - cycle_baselines
    - pattern_results
    - early_feedback
    - audit_events

Revision: 0001
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # daily_logs
    # ------------------------------------------------------------------
    op.create_table(
        "daily_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("logged_date", sa.String(10), nullable=False),
        sa.Column("pain_level", sa.SmallInteger, nullable=False),
        sa.Column("energy_level", sa.SmallInteger, nullable=False),
        sa.Column("mood_level", sa.SmallInteger, nullable=True),
        sa.Column("dominant_symptom", sa.String(32), nullable=False),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("cycle_day", sa.SmallInteger, nullable=False),
        sa.Column("cycle_phase", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.UniqueConstraint(
            "user_id", "logged_date", "is_active",
            name="uq_daily_logs_user_date_active",
        ),
    )
    op.create_index("ix_daily_logs_user_id", "daily_logs", ["user_id"])
    op.create_index(
        "ix_daily_logs_user_date",
        "daily_logs",
        ["user_id", "logged_date"],
    )

    # ------------------------------------------------------------------
    # cycle_baselines
    # ------------------------------------------------------------------
    op.create_table(
        "cycle_baselines",
        sa.Column("user_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("last_period_start", sa.String(10), nullable=False),
        sa.Column("average_cycle_length", sa.SmallInteger, nullable=True),
        sa.Column("is_irregular", sa.Boolean, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )

    # ------------------------------------------------------------------
    # pattern_results
    # ------------------------------------------------------------------
    op.create_table(
        "pattern_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("generated_at", sa.DateTime, nullable=False),
        sa.Column("cycles_analyzed", sa.SmallInteger, nullable=False),
        sa.Column("total_logs", sa.Integer, nullable=False),
        sa.Column("onset_range_start", sa.SmallInteger, nullable=False),
        sa.Column("onset_range_end", sa.SmallInteger, nullable=False),
        sa.Column("escalation_speed", sa.String(16), nullable=False),
        sa.Column("severity_trend", sa.String(24), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
    )
    op.create_index("ix_pattern_results_user_id", "pattern_results", ["user_id"])

    # ------------------------------------------------------------------
    # early_feedback
    # ------------------------------------------------------------------
    op.create_table(
        "early_feedback",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("generated_at", sa.DateTime, nullable=False),
        sa.Column("log_count", sa.SmallInteger, nullable=False),
        sa.Column("trigger_phase", sa.String(16), nullable=True),
    )
    op.create_index("ix_early_feedback_user_id", "early_feedback", ["user_id"])

    # ------------------------------------------------------------------
    # audit_events
    # ------------------------------------------------------------------
    op.create_table(
        "audit_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("occurred_at", sa.DateTime, nullable=False),
        sa.Column("payload", JSONB, nullable=False),
    )
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"])
    op.create_index("ix_audit_events_user_id", "audit_events", ["user_id"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("early_feedback")
    op.drop_table("pattern_results")
    op.drop_table("cycle_baselines")
    op.drop_table("daily_logs")
