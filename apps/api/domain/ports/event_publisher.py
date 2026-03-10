"""
IEventPublisher

The interface for publishing domain events.

Every mutation to health data emits a domain event. The application
layer calls this publisher after a successful write. The infrastructure
layer decides what to do with the event — write it to the audit log,
send a notification, trigger a background job.

The domain and application layers only know about this interface.
They never know whether events go to a database, a queue, or both.

Design note:
- publish() accepts a single event. Call it once per event.
- publish_all() is a convenience for use cases that emit multiple
  events in one operation (e.g. LogSuperseded emits both
  LogSuperseded and LogCreated).
- Both methods are fire-and-forget from the caller's perspective.
  Error handling is the infrastructure layer's responsibility.
"""

from abc import ABC, abstractmethod

from domain.models.events import DomainEvent


class IEventPublisher(ABC):

    @abstractmethod
    def publish(self, event: DomainEvent) -> None:
        """
        Publish a single domain event.

        The infrastructure implementation writes this to the
        audit_events table and dispatches any side effects.
        """
        ...

    @abstractmethod
    def publish_all(self, events: list[DomainEvent]) -> None:
        """
        Publish multiple domain events in order.

        Events are processed in list order. If the infrastructure
        implementation is transactional, all events in the list
        are written atomically.
        """
        ...
