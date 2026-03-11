"""
infrastructure.events.publisher

DatabaseEventPublisher — writes domain events to the audit_events table.

Every health data mutation emits a domain event. This publisher writes
those events synchronously to the audit_events table within the same
database transaction as the mutation that triggered them.

This means events and data are always consistent — if the mutation rolls
back, the events roll back with it. There is no window where the data
exists but the audit trail does not.

The tradeoff: events do not fan out to external systems (queues, webhooks,
notifications) in this implementation. That is intentional for the MVP.
When external dispatch is needed, this class can be extended or replaced
with a publisher that writes to the audit table AND enqueues to a message
broker. The application layer never changes — it only calls IEventPublisher.

Serialization:
    Domain events are dataclasses. We convert them to dicts using
    dataclasses.asdict(), which handles nested dataclasses recursively.
    UUID and datetime fields need explicit string conversion because
    JSON does not natively support these types.
"""

from __future__ import annotations

import dataclasses
from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from domain.models.events import DomainEvent
from domain.ports import IEventPublisher
from infrastructure.orm.tables import audit_events


class DatabaseEventPublisher(IEventPublisher):

    def __init__(self, session: Session) -> None:
        self._session = session

    def publish(self, event: DomainEvent) -> None:
        self._write(event)

    def publish_all(self, events: list[DomainEvent]) -> None:
        for event in events:
            self._write(event)

    def _write(self, event: DomainEvent) -> None:
        payload = _event_to_dict(event)
        self._session.execute(
            audit_events.insert().values(
                id=uuid4(),
                event_type=type(event).__name__,
                user_id=_extract_user_id(event),
                occurred_at=event.occurred_at,
                payload=payload,
            )
        )


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _event_to_dict(event: DomainEvent) -> dict[str, Any]:
    """
    Convert a domain event dataclass to a JSON-safe dict.

    dataclasses.asdict() handles nested dataclasses. We then walk the
    result and convert any UUID, date, or datetime values to strings.
    """
    raw = dataclasses.asdict(event)
    return _sanitize(raw)


def _sanitize(obj: Any) -> Any:
    """Recursively convert non-JSON-serializable values to strings."""
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return obj


def _extract_user_id(event: DomainEvent) -> UUID | None:
    """
    Extract user_id from an event if present.

    Most events carry a user_id. System events may not.
    Returns None rather than raising if the field is absent.
    """
    return getattr(event, "user_id", None)
