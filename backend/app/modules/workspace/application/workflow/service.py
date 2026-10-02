"""Workflow Event Service — append, fold, idempotency helpers."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

from app.modules.workspace.application.workflow.events import (
    AUDIT_ACTION_FOR_EVENT,
    WorkflowEvent,
    WorkflowEventType,
)
from app.modules.workspace.application.workflow.fold import (
    FoldedWorkflowState,
    already_recorded,
    fold_events,
)
from app.modules.workspace.application.workflow.repository import (
    WorkflowEventRepositoryProtocol,
)


class WorkflowEventService:
    """Single seam between API dependencies and Workflow Event Store + fold."""

    def __init__(self, repository: WorkflowEventRepositoryProtocol) -> None:
        self._repository = repository

    async def list_events(self, session_id: int) -> Sequence[WorkflowEvent]:
        return await self._repository.list_for_session(session_id)

    async def append_event(
        self,
        *,
        session_id: int,
        actor_user_id: int | None,
        event_type: WorkflowEventType,
        object_id: str | None = None,
        context_hash: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> WorkflowEvent:
        return await self._repository.append(
            session_id=session_id,
            actor_user_id=actor_user_id,
            event_type=event_type,
            object_id=object_id,
            context_hash=context_hash,
            payload=payload,
        )

    async def get_folded_state(
        self,
        session_id: int,
        context_hash: str,
    ) -> FoldedWorkflowState:
        events = await self._repository.list_for_session(session_id)
        return fold_events(events, current_context_hash=context_hash)

    async def append_if_not_recorded(
        self,
        *,
        session_id: int,
        actor_user_id: int | None,
        event_type: WorkflowEventType,
        object_id: str | None = None,
        context_hash: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> tuple[WorkflowEvent | None, bool]:
        """Append unless an identical mutation already exists for this epoch.

        Returns ``(event_or_None, was_duplicate)``.
        """
        events = await self._repository.list_for_session(session_id)
        if already_recorded(
            events,
            event_type,
            object_id=object_id,
            context_hash=context_hash,
        ):
            return None, True
        event = await self.append_event(
            session_id=session_id,
            actor_user_id=actor_user_id,
            event_type=event_type,
            object_id=object_id,
            context_hash=context_hash,
            payload=payload,
        )
        return event, False

    async def record_workspace_opened_once(
        self,
        *,
        session_id: int,
        actor_user_id: int | None,
        context_hash: str | None = None,
    ) -> bool:
        """Append WorkspaceOpened at most once per (session, actor) per UTC day."""
        events = await self._repository.list_for_session(session_id)
        today = datetime.now(timezone.utc).date()
        for event in events:
            if event.event_type is not WorkflowEventType.WORKSPACE_OPENED:
                continue
            if actor_user_id is not None and event.actor_user_id != actor_user_id:
                continue
            if event.created_at is not None:
                created = event.created_at
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                if created.astimezone(timezone.utc).date() == today:
                    return False
            else:
                return False
        await self.append_event(
            session_id=session_id,
            actor_user_id=actor_user_id,
            event_type=WorkflowEventType.WORKSPACE_OPENED,
            context_hash=context_hash,
        )
        return True

    @staticmethod
    def audit_action_for(event_type: WorkflowEventType) -> str:
        return AUDIT_ACTION_FOR_EVENT.get(event_type, event_type.value)
