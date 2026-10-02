"""Immutable Workflow Event types — canonical clinical workflow persistence."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class WorkflowEventType(str, Enum):
    """Canonical workflow events (doctor-clinical-workflow.md §8.1)."""

    WORKSPACE_OPENED = "WorkspaceOpened"
    CARD_VIEWED = "CardViewed"
    TIMELINE_EXPANDED = "TimelineExpanded"
    QUEUE_ITEM_VIEWED = "QueueItemViewed"
    QUEUE_ITEM_ACKNOWLEDGED = "QueueItemAcknowledged"
    QUEUE_ITEM_RESOLVED = "QueueItemResolved"
    QUEUE_ITEM_DISMISSED = "QueueItemDismissed"
    STORY_REFRESH_REQUESTED = "StoryRefreshRequested"
    STORY_REFRESH_COMPLETED = "StoryRefreshCompleted"
    STORY_REFRESH_FAILED = "StoryRefreshFailed"
    SOURCE_DOCUMENT_OPENED = "SourceDocumentOpened"
    EVIDENCE_VIEWED = "EvidenceViewed"
    EXPLANATION_VIEWED = "ExplanationViewed"
    SESSION_CLOSED = "SessionClosed"


# Observational AuditLog snake_case mirrors (never used for reconstruction).
AUDIT_ACTION_FOR_EVENT: dict[WorkflowEventType, str] = {
    WorkflowEventType.WORKSPACE_OPENED: "view_workspace",
    WorkflowEventType.CARD_VIEWED: "card_viewed",
    WorkflowEventType.TIMELINE_EXPANDED: "timeline_expanded",
    WorkflowEventType.QUEUE_ITEM_VIEWED: "queue_item_viewed",
    WorkflowEventType.QUEUE_ITEM_ACKNOWLEDGED: "queue_item_acknowledged",
    WorkflowEventType.QUEUE_ITEM_RESOLVED: "queue_item_resolved",
    WorkflowEventType.QUEUE_ITEM_DISMISSED: "queue_item_dismissed",
    WorkflowEventType.STORY_REFRESH_REQUESTED: "story_refresh_requested",
    WorkflowEventType.STORY_REFRESH_COMPLETED: "story_refresh_completed",
    WorkflowEventType.STORY_REFRESH_FAILED: "story_refresh_failed",
    WorkflowEventType.SOURCE_DOCUMENT_OPENED: "source_document_opened",
    WorkflowEventType.EVIDENCE_VIEWED: "evidence_viewed",
    WorkflowEventType.EXPLANATION_VIEWED: "explanation_viewed",
    WorkflowEventType.SESSION_CLOSED: "session_closed",
}


class WorkflowEvent(BaseModel):
    """Immutable workflow event record (domain projection of the event store)."""

    model_config = ConfigDict(frozen=True)

    id: int | None = None
    session_id: int
    actor_user_id: int | None = None
    event_type: WorkflowEventType
    object_id: str | None = None
    context_hash: str | None = None
    payload: dict[str, Any] | None = None
    created_at: datetime | None = None
