"""Workflow Event Store repository protocol (no infrastructure imports)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

from app.modules.workspace.application.workflow.events import (
    WorkflowEvent,
    WorkflowEventType,
)


class WorkflowEventRepositoryProtocol(Protocol):
    """Append-only persistence for immutable workflow events."""

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
        """Persist one immutable event; return the stored projection."""
        ...

    async def list_for_session(self, session_id: int) -> Sequence[WorkflowEvent]:
        """Return all events for a session ordered oldest → newest."""
        ...
