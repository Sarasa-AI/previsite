"""Plan eligibility helpers for workflow mutations (application layer)."""

from __future__ import annotations

from app.modules.workspace.application.inputs import ReviewAcknowledgements
from app.modules.workspace.domain.enums import AttentionSlot, ClinicalObjectId
from app.modules.workspace.domain.models import WorkspacePlan


def is_acknowledgeable(
    plan: WorkspacePlan,
    object_id: ClinicalObjectId,
    review: ReviewAcknowledgements,
) -> bool:
    """True when the object currently requires acknowledgement, or is already ack'd (idempotent)."""
    if object_id in review.acknowledged_objects:
        return True
    item = next(
        (i for i in plan.decision_queue.items if i.object_id is object_id),
        None,
    )
    if item is not None and item.acknowledge_required:
        return True
    directive = next(
        (d for d in plan.layout_directives if d.object_id is object_id),
        None,
    )
    return (
        directive is not None
        and "acknowledge_required" in directive.flags
        and directive.slot is not AttentionSlot.HIDDEN
    )


def is_resolvable(
    plan: WorkspacePlan,
    object_id: ClinicalObjectId,
    review: ReviewAcknowledgements,
) -> bool:
    """True when the object is active in the plan, or already resolved (idempotent)."""
    if object_id in review.resolved_objects:
        return True
    if any(i.object_id is object_id for i in plan.decision_queue.items):
        return True
    directive = next(
        (d for d in plan.layout_directives if d.object_id is object_id),
        None,
    )
    return directive is not None and directive.slot is not AttentionSlot.HIDDEN


def is_dismissible(
    plan: WorkspacePlan,
    object_id: ClinicalObjectId,
    review: ReviewAcknowledgements,
) -> bool:
    """True when the object is visible, or already dismissed (idempotent)."""
    if object_id in review.dismissed_objects:
        return True
    directive = next(
        (d for d in plan.layout_directives if d.object_id is object_id),
        None,
    )
    return directive is not None and directive.slot is not AttentionSlot.HIDDEN
