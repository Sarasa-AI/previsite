"""In-memory Workflow Event Store — for unit / API wiring tests."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

from app.modules.workspace.application.workflow.events import (
    WorkflowEvent,
    WorkflowEventType,
)


class InMemoryWorkflowEventRepository:
    """Append-only in-memory event store (no SQLAlchemy)."""

    def __init__(self) -> None:
        self._events: list[WorkflowEvent] = []
        self._next_id = 1

    async def append(
        self,
        *,
        session_id: int,
        actor_user_id: int | None,
        event_type: WorkflowEventType,
        object_id: str | None = None,
        context_hash: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> WorkflowEvent:
        event = WorkflowEvent(
            id=self._next_id,
            session_id=session_id,
            actor_user_id=actor_user_id,
            event_type=event_type,
            object_id=object_id,
            context_hash=context_hash,
            payload=payload,
            created_at=datetime.now(timezone.utc),
        )
        self._next_id += 1
        self._events.append(event)
        return event

    async def list_for_session(self, session_id: int) -> Sequence[WorkflowEvent]:
        return tuple(e for e in self._events if e.session_id == session_id)

    def clear(self) -> None:
        self._events.clear()
        self._next_id = 1
