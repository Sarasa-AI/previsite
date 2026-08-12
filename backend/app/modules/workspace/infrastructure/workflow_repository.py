"""SQLAlchemy implementation of the Workflow Event Store repository."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.workspace.application.workflow.events import (
    WorkflowEvent,
    WorkflowEventType,
)
from app.modules.workspace.infrastructure.models import WorkflowEventRecord


class SqlAlchemyWorkflowEventRepository:
    """Append-only Workflow Event Store backed by ``workflow_events``."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

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
        row = WorkflowEventRecord(
            session_id=session_id,
            actor_user_id=actor_user_id,
            event_type=event_type.value,
            object_id=object_id,
            context_hash=context_hash,
            payload=json.dumps(payload) if payload is not None else None,
        )
        self._db.add(row)
        await self._db.commit()
        await self._db.refresh(row)
        return self._to_domain(row)

    async def list_for_session(self, session_id: int) -> Sequence[WorkflowEvent]:
        result = await self._db.execute(
            select(WorkflowEventRecord)
            .where(WorkflowEventRecord.session_id == session_id)
            .order_by(WorkflowEventRecord.id.asc())
        )
        rows = result.scalars().all()
        return tuple(self._to_domain(row) for row in rows)

    @staticmethod
    def _to_domain(row: WorkflowEventRecord) -> WorkflowEvent:
        payload: dict[str, Any] | None = None
        if row.payload:
            try:
                parsed = json.loads(row.payload)
                if isinstance(parsed, dict):
                    payload = parsed
            except (TypeError, ValueError):
                payload = None
        return WorkflowEvent(
            id=row.id,
            session_id=row.session_id,
            actor_user_id=row.actor_user_id,
            event_type=WorkflowEventType(row.event_type),
            object_id=row.object_id,
            context_hash=row.context_hash,
            payload=payload,
            created_at=row.created_at,
        )
