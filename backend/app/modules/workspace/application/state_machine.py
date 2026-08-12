"""Workspace state machine — derived from session signals and plan readiness."""

from __future__ import annotations

from app.modules.workspace.application.inputs import ReviewAcknowledgements
from app.modules.workspace.application.signals import WorkspaceSignals
from app.modules.workspace.domain.enums import (
    ClinicalObjectId,
    PriorityLevel,
    VisibilityReason,
    WorkspaceState,
)
from app.modules.workspace.domain.models import DecisionQueue, LayoutDirective


def _is_effectively_acknowledged(
    object_id: ClinicalObjectId,
    review: ReviewAcknowledgements,
) -> bool:
    """Ack gates clear via explicit acknowledgement OR clinical resolve (§6.3)."""
    return (
        object_id in review.acknowledged_objects
        or object_id in review.resolved_objects
    )


def _p0_still_pending(directive, review: ReviewAcknowledgements) -> bool:
    """P0 gate remains pending until ack/resolve.

    Physician dismiss hides the card but does NOT clear P0 ack gates (§6.4).
    True no_data / specialty_filter hides are excluded from the pending set.
    """
    if directive.priority is not PriorityLevel.P0:
        return False
    if _is_effectively_acknowledged(directive.object_id, review):
        return False
    if directive.slot.value != "hidden":
        return True
    # Dismissed P0 still counts as a pending gate.
    return directive.visibility_reason is VisibilityReason.PHYSICIAN_DISMISSED


def compute_workspace_state(
    signals: WorkspaceSignals,
    directives: tuple[LayoutDirective, ...],
    queue: DecisionQueue,
    review: ReviewAcknowledgements,
    *,
    context_available: bool,
) -> WorkspaceState:
    if signals.offline:
        return WorkspaceState.OFFLINE
    if signals.session_locked:
        return WorkspaceState.READ_ONLY
    if not context_available:
        return WorkspaceState.LOADING

    if signals.soap_status in {"pending", "generating"}:
        return WorkspaceState.GENERATING

    if signals.validated_conflicts:
        # Conflicts present until acknowledged or resolved
        conflict_dir = next(
            (d for d in directives if d.object_id is ClinicalObjectId.CONFLICTS),
            None,
        )
        if (
            conflict_dir
            and conflict_dir.priority is PriorityLevel.P0
            and not _is_effectively_acknowledged(
                ClinicalObjectId.CONFLICTS, review
            )
        ):
            return WorkspaceState.CONFLICT_PRESENT

    p0_pending = [
        d.object_id for d in directives if _p0_still_pending(d, review)
    ]
    if p0_pending or (
        queue.items
        and any(i.acknowledge_required for i in queue.items)
    ):
        return WorkspaceState.REVIEW_NEEDED

    if signals.soap_status == "ready":
        if signals.verification_status == "verified" and not signals.validated_conflicts:
            if signals.soap_accepted and not p0_pending:
                return WorkspaceState.COMPLETED
            return WorkspaceState.VERIFIED
        if signals.verification_status == "partially_verified":
            return WorkspaceState.PARTIALLY_VERIFIED
        return WorkspaceState.REVIEW_NEEDED

    return WorkspaceState.REVIEW_NEEDED
