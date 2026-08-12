"""Pure fold logic tests — Workflow Event Store → ReviewAcknowledgements."""

from __future__ import annotations

from datetime import datetime, timezone

from app.modules.workspace.application.workflow.events import (
    WorkflowEvent,
    WorkflowEventType,
)
from app.modules.workspace.application.workflow.fold import (
    already_recorded,
    fold_events,
    fold_story_status,
)
from app.modules.workspace.domain.enums import ClinicalObjectId

HASH_A = "aaa"
HASH_B = "bbb"
NOW = datetime(2026, 8, 4, 12, 0, 0, tzinfo=timezone.utc)


def _event(
    event_type: WorkflowEventType,
    *,
    object_id: str | None = None,
    context_hash: str | None = HASH_A,
    session_id: int = 1,
) -> WorkflowEvent:
    return WorkflowEvent(
        session_id=session_id,
        actor_user_id=7,
        event_type=event_type,
        object_id=object_id,
        context_hash=context_hash,
        created_at=NOW,
    )


def test_fold_acknowledge_resolve_dismiss_sets() -> None:
    events = [
        _event(WorkflowEventType.QUEUE_ITEM_VIEWED, object_id="conflicts"),
        _event(WorkflowEventType.QUEUE_ITEM_ACKNOWLEDGED, object_id="conflicts"),
        _event(WorkflowEventType.QUEUE_ITEM_RESOLVED, object_id="red_flags"),
        _event(WorkflowEventType.QUEUE_ITEM_DISMISSED, object_id="labs"),
    ]
    folded = fold_events(events, current_context_hash=HASH_A)
    review = folded.review_state
    assert ClinicalObjectId.CONFLICTS in review.acknowledged_objects
    assert ClinicalObjectId.CONFLICTS in review.viewed_objects
    assert ClinicalObjectId.RED_FLAGS in review.resolved_objects
    assert ClinicalObjectId.LABS in review.dismissed_objects
    assert folded.version == "4"
    assert folded.story_status == "ready"


def test_fold_scopes_to_current_context_hash() -> None:
    events = [
        _event(
            WorkflowEventType.QUEUE_ITEM_ACKNOWLEDGED,
            object_id="conflicts",
            context_hash=HASH_A,
        ),
        _event(
            WorkflowEventType.QUEUE_ITEM_DISMISSED,
            object_id="labs",
            context_hash=HASH_B,
        ),
    ]
    folded = fold_events(events, current_context_hash=HASH_A)
    assert ClinicalObjectId.CONFLICTS in folded.review_state.acknowledged_objects
    assert ClinicalObjectId.LABS not in folded.review_state.dismissed_objects


def test_fold_replay_is_deterministic() -> None:
    events = [
        _event(WorkflowEventType.QUEUE_ITEM_ACKNOWLEDGED, object_id="allergies"),
        _event(WorkflowEventType.QUEUE_ITEM_RESOLVED, object_id="medications"),
    ]
    a = fold_events(events, current_context_hash=HASH_A)
    b = fold_events(events, current_context_hash=HASH_A)
    assert a.review_state == b.review_state
    assert a.version == b.version
    assert a.story_status == b.story_status


def test_fold_idempotent_duplicate_acks_are_set_valued() -> None:
    events = [
        _event(WorkflowEventType.QUEUE_ITEM_ACKNOWLEDGED, object_id="conflicts"),
        _event(WorkflowEventType.QUEUE_ITEM_ACKNOWLEDGED, object_id="conflicts"),
    ]
    folded = fold_events(events, current_context_hash=HASH_A)
    assert len(folded.review_state.acknowledged_objects) == 1
    assert ClinicalObjectId.CONFLICTS in folded.review_state.acknowledged_objects


def test_fold_story_status_generating_then_ready() -> None:
    requested = [
        _event(WorkflowEventType.STORY_REFRESH_REQUESTED),
    ]
    assert fold_story_status(requested, HASH_A) == "generating"
    folded = fold_events(requested, current_context_hash=HASH_A)
    assert folded.review_state.story_refresh_requested is True

    completed = requested + [_event(WorkflowEventType.STORY_REFRESH_COMPLETED)]
    assert fold_story_status(completed, HASH_A) == "ready"
    folded2 = fold_events(completed, current_context_hash=HASH_A)
    assert folded2.review_state.story_refresh_requested is False


def test_fold_story_status_failed() -> None:
    events = [
        _event(WorkflowEventType.STORY_REFRESH_REQUESTED),
        _event(WorkflowEventType.STORY_REFRESH_FAILED),
    ]
    assert fold_story_status(events, HASH_A) == "failed"
    folded = fold_events(events, current_context_hash=HASH_A)
    assert folded.review_state.story_frozen is True


def test_already_recorded_idempotency_helper() -> None:
    events = [
        _event(WorkflowEventType.QUEUE_ITEM_RESOLVED, object_id="labs"),
    ]
    assert already_recorded(
        events,
        WorkflowEventType.QUEUE_ITEM_RESOLVED,
        object_id="labs",
        context_hash=HASH_A,
    )
    assert not already_recorded(
        events,
        WorkflowEventType.QUEUE_ITEM_RESOLVED,
        object_id="labs",
        context_hash=HASH_B,
    )
    assert not already_recorded(
        events,
        WorkflowEventType.QUEUE_ITEM_DISMISSED,
        object_id="labs",
        context_hash=HASH_A,
    )


def test_session_closed_flag() -> None:
    events = [_event(WorkflowEventType.SESSION_CLOSED, context_hash=None)]
    folded = fold_events(events, current_context_hash=HASH_A)
    assert folded.session_closed is True
