"""Pure fold: Workflow Event Store → ReviewAcknowledgements / story status."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from app.modules.workspace.application.inputs import ReviewAcknowledgements
from app.modules.workspace.application.workflow.events import (
    WorkflowEvent,
    WorkflowEventType,
)
from app.modules.workspace.domain.enums import ClinicalObjectId

StoryStatus = Literal["ready", "refresh_requested", "generating", "failed"]


@dataclass(frozen=True)
class FoldedWorkflowState:
    """Folded workflow inputs consumed by the next WorkspaceOrchestrator.compute()."""

    review_state: ReviewAcknowledgements
    version: str
    story_status: StoryStatus
    session_closed: bool = False


def _parse_object_id(raw: str | None) -> ClinicalObjectId | None:
    if not raw:
        return None
    try:
        return ClinicalObjectId(raw)
    except ValueError:
        return None


def _in_current_epoch(event: WorkflowEvent, current_context_hash: str) -> bool:
    """Active suppressions / acks are scoped to the current context_hash (§4.4)."""
    if not current_context_hash:
        return True
    if event.context_hash is None:
        return True
    return event.context_hash == current_context_hash


def fold_story_status(
    events: Sequence[WorkflowEvent],
    current_context_hash: str,
) -> StoryStatus:
    """Derive story refresh lifecycle phase from the latest story event in-epoch."""
    latest: WorkflowEventType | None = None
    for event in events:
        if event.event_type not in {
            WorkflowEventType.STORY_REFRESH_REQUESTED,
            WorkflowEventType.STORY_REFRESH_COMPLETED,
            WorkflowEventType.STORY_REFRESH_FAILED,
        }:
            continue
        if not _in_current_epoch(event, current_context_hash):
            continue
        latest = event.event_type

    if latest is WorkflowEventType.STORY_REFRESH_REQUESTED:
        # Synchronous engine treats requested as generating until completed/failed.
        return "generating"
    if latest is WorkflowEventType.STORY_REFRESH_FAILED:
        return "failed"
    return "ready"


def fold_events(
    events: Sequence[WorkflowEvent],
    *,
    current_context_hash: str,
) -> FoldedWorkflowState:
    """Fold immutable events into ReviewAcknowledgements + story status.

    Ack / resolve / dismiss / viewed membership is set-valued and scoped to the
    current context_hash epoch. Story flags derive from the latest story event.
    """
    viewed: set[ClinicalObjectId] = set()
    acknowledged: set[ClinicalObjectId] = set()
    resolved: set[ClinicalObjectId] = set()
    dismissed: set[ClinicalObjectId] = set()
    story_refresh_requested = False
    story_frozen = False
    session_closed = False

    for event in events:
        if event.event_type is WorkflowEventType.SESSION_CLOSED:
            session_closed = True

        if not _in_current_epoch(event, current_context_hash):
            continue

        oid = _parse_object_id(event.object_id)

        if event.event_type is WorkflowEventType.QUEUE_ITEM_VIEWED and oid is not None:
            viewed.add(oid)
        elif (
            event.event_type is WorkflowEventType.QUEUE_ITEM_ACKNOWLEDGED
            and oid is not None
        ):
            viewed.add(oid)
            acknowledged.add(oid)
        elif (
            event.event_type is WorkflowEventType.QUEUE_ITEM_RESOLVED
            and oid is not None
        ):
            viewed.add(oid)
            resolved.add(oid)
        elif (
            event.event_type is WorkflowEventType.QUEUE_ITEM_DISMISSED
            and oid is not None
        ):
            viewed.add(oid)
            dismissed.add(oid)
        elif event.event_type is WorkflowEventType.STORY_REFRESH_REQUESTED:
            story_refresh_requested = True
            story_frozen = False
        elif event.event_type is WorkflowEventType.STORY_REFRESH_COMPLETED:
            story_refresh_requested = False
            story_frozen = False
        elif event.event_type is WorkflowEventType.STORY_REFRESH_FAILED:
            story_refresh_requested = False
            # Failed refresh leaves prior story potentially stale / frozen.
            story_frozen = True

    story_status = fold_story_status(events, current_context_hash)
    # Surface refresh_requested distinctly when status is mid-flight.
    if story_status in {"generating", "refresh_requested"}:
        story_refresh_requested = True

    review = ReviewAcknowledgements(
        acknowledged_objects=frozenset(acknowledged),
        viewed_objects=frozenset(viewed),
        resolved_objects=frozenset(resolved),
        dismissed_objects=frozenset(dismissed),
        story_refresh_requested=story_refresh_requested,
        story_frozen=story_frozen,
    )
    return FoldedWorkflowState(
        review_state=review,
        version=str(len(events)),
        story_status=story_status,
        session_closed=session_closed,
    )


def already_recorded(
    events: Sequence[WorkflowEvent],
    event_type: WorkflowEventType,
    *,
    object_id: str | None,
    context_hash: str | None,
) -> bool:
    """True when an identical mutation event already exists for this context epoch."""
    for event in events:
        if event.event_type is not event_type:
            continue
        if object_id is not None and event.object_id != object_id:
            continue
        if context_hash is not None and event.context_hash != context_hash:
            continue
        return True
    return False
