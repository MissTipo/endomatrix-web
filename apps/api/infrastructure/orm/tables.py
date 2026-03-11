"""
infrastructure.orm.tables

SQLAlchemy Core Table definitions for EndoMatrix.

These are the schema as code. Alembic generates migrations from these.

Design rules:
- These are NOT ORM classes. They are plain Table objects.
  The repositories do the row-to-domain-model translation manually.
  Domain models stay free of SQLAlchemy decorators.
- All primary keys are UUIDs, never serial integers.
  This matters for future multi-region and data portability.
- Columns that are system-set (cycle_day, cycle_phase, created_at)
  are NOT nullable in the database — they must always be provided
  by the application at write time.
- Columns that are user-optional (mood_level, note) are nullable.
- JSONB is used for complex nested outputs (PatternResult payload)
  that are written once and read as a whole, never queried relationally.

Tables defined here:
    daily_logs        — one row per active or superseded daily log
    cycle_baselines   — one row per user, upserted on each baseline change
    pattern_results   — one row per analysis run (append-only)
    early_feedback    — one row per generated feedback message
    audit_events      — append-only event log (never updated or deleted)
"""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    MetaData,
    SmallInteger,
    String,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

# Single metadata instance shared across all tables.
# Alembic reads this at migration time.
metadata = MetaData()


# ---------------------------------------------------------------------------
# daily_logs
# ---------------------------------------------------------------------------

daily_logs = Table(
    "daily_logs",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("user_id", UUID(as_uuid=True), nullable=False, index=True),
    Column("logged_date", String(10), nullable=False),      # ISO date: "YYYY-MM-DD"
    Column("pain_level", SmallInteger, nullable=False),
    Column("energy_level", SmallInteger, nullable=False),
    Column("mood_level", SmallInteger, nullable=True),      # MVP field
    Column("dominant_symptom", String(32), nullable=False), # Symptom enum value
    Column("note", Text, nullable=True),                    # MVP field, max 280 chars
    Column("cycle_day", SmallInteger, nullable=False),
    Column("cycle_phase", String(16), nullable=False),      # CyclePhase enum value
    Column("created_at", DateTime, nullable=False),
    Column("is_active", Boolean, nullable=False, default=True, server_default="true"),
)

# Partial unique index: enforce at most one active log per user per date.
# Using a partial index (WHERE is_active = true) rather than a full unique
# constraint on (user_id, logged_date, is_active) so that multiple superseded
# (is_active=false) rows can exist for the same user/date — preserving the
# full audit trail across corrections.
Index(
    "uix_daily_logs_user_date_active",
    daily_logs.c.user_id,
    daily_logs.c.logged_date,
    unique=True,
    postgresql_where=(daily_logs.c.is_active == True),  # noqa: E712
)


# ---------------------------------------------------------------------------
# cycle_baselines
# ---------------------------------------------------------------------------

cycle_baselines = Table(
    "cycle_baselines",
    metadata,
    Column("user_id", UUID(as_uuid=True), primary_key=True),
    Column("last_period_start", String(10), nullable=False),    # ISO date
    Column("average_cycle_length", SmallInteger, nullable=True),# None = irregular
    Column("is_irregular", Boolean, nullable=False),
    Column("updated_at", DateTime, nullable=False),
)


# ---------------------------------------------------------------------------
# pattern_results
# ---------------------------------------------------------------------------

pattern_results = Table(
    "pattern_results",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("user_id", UUID(as_uuid=True), nullable=False, index=True),
    Column("generated_at", DateTime, nullable=False),
    Column("cycles_analyzed", SmallInteger, nullable=False),
    Column("total_logs", Integer, nullable=False),
    # Scalar fields stored as typed columns for easy querying
    Column("onset_range_start", SmallInteger, nullable=False),
    Column("onset_range_end", SmallInteger, nullable=False),
    Column("escalation_speed", String(16), nullable=False),     # EscalationSpeed value
    Column("severity_trend", String(24), nullable=False),       # SeverityTrend value
    # Complex nested output stored as JSONB — written once, read as a whole
    # Contains: symptom_clusters, phase_patterns, prediction
    Column("payload", JSONB, nullable=False),
)


# ---------------------------------------------------------------------------
# early_feedback
# ---------------------------------------------------------------------------

early_feedback = Table(
    "early_feedback",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("user_id", UUID(as_uuid=True), nullable=False, index=True),
    Column("message", Text, nullable=False),
    Column("generated_at", DateTime, nullable=False),
    Column("log_count", SmallInteger, nullable=False),
    Column("trigger_phase", String(16), nullable=True),  # CyclePhase value, nullable
)


# ---------------------------------------------------------------------------
# audit_events
# ---------------------------------------------------------------------------
# Append-only. Never updated. Never deleted except by compliance workflows.
# DataDeletionRequested events are retained even when user data is removed.

audit_events = Table(
    "audit_events",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("event_type", String(64), nullable=False, index=True),
    Column("user_id", UUID(as_uuid=True), nullable=True, index=True),
    # user_id is nullable because some system events are not user-scoped
    Column("occurred_at", DateTime, nullable=False),
    Column("payload", JSONB, nullable=False),
    # No update columns. No soft-delete. This table is a ledger.
)
