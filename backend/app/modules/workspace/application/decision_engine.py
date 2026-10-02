"""Decision Engine — deterministic recommended review order."""

from __future__ import annotations

from app.modules.workspace.application.explanation_templates import explanation_for
from app.modules.workspace.application.lens_weights import lens_weight
from app.modules.workspace.application.role_profiles import RoleClamp
from app.modules.workspace.domain.enums import (
    AttentionSlot,
    ClinicalObjectId,
    PriorityLevel,
    ReasonCode,
    SpecialtyLens,
    TrustProvenance,
    TrustVerification,
)
from app.modules.workspace.domain.models import (
    DecisionQueue,
    DecisionQueueItem,
    LayoutDirective,
)

# Attention Model default rank (spec §4.1 / §3.4 tie-break)
_ATTENTION_RANK: dict[ClinicalObjectId, int] = {
    ClinicalObjectId.CONFLICTS: 0,
    ClinicalObjectId.ALLERGIES: 1,
    ClinicalObjectId.RED_FLAGS: 2,
    ClinicalObjectId.CRITICAL_LABS: 3,
    ClinicalObjectId.CRITICAL_ALERTS: 4,
    ClinicalObjectId.CHIEF_COMPLAINT: 5,
    ClinicalObjectId.MISSING_DATA: 6,
    ClinicalObjectId.STORY: 7,
    ClinicalObjectId.TIMELINE: 8,
    ClinicalObjectId.LABS: 9,
    ClinicalObjectId.MEDICATIONS: 10,
    ClinicalObjectId.PATIENT_QUESTIONS: 11,
    ClinicalObjectId.PMH: 12,
    ClinicalObjectId.SOAP: 13,
    ClinicalObjectId.DOCUMENTS: 14,
    ClinicalObjectId.SNAPSHOT: 15,
}

_PRIORITY_RANK = {
    PriorityLevel.P0: 0,
    PriorityLevel.P1: 1,
    PriorityLevel.P2: 2,
    PriorityLevel.P3: 3,
}

_REASON_FOR: dict[ClinicalObjectId, ReasonCode] = {
    ClinicalObjectId.CONFLICTS: ReasonCode.SAFETY,
    ClinicalObjectId.ALLERGIES: ReasonCode.SAFETY,
    ClinicalObjectId.RED_FLAGS: ReasonCode.SAFETY,
    ClinicalObjectId.CRITICAL_LABS: ReasonCode.SAFETY,
    ClinicalObjectId.CRITICAL_ALERTS: ReasonCode.SAFETY,
    ClinicalObjectId.MISSING_DATA: ReasonCode.SAFETY,
    ClinicalObjectId.CHIEF_COMPLAINT: ReasonCode.ORIENT,
    ClinicalObjectId.STORY: ReasonCode.ORIENT,
    ClinicalObjectId.TIMELINE: ReasonCode.EVIDENCE,
    ClinicalObjectId.LABS: ReasonCode.EVIDENCE,
    ClinicalObjectId.MEDICATIONS: ReasonCode.EVIDENCE,
    ClinicalObjectId.PATIENT_QUESTIONS: ReasonCode.OPEN_LOOP,
    ClinicalObjectId.SOAP: ReasonCode.DOCUMENT,
    ClinicalObjectId.DOCUMENTS: ReasonCode.DOCUMENT,
    ClinicalObjectId.PMH: ReasonCode.DOCUMENT,
    ClinicalObjectId.SNAPSHOT: ReasonCode.DOCUMENT,
}


def build_decision_queue(
    directives: tuple[LayoutDirective, ...],
    lens: SpecialtyLens,
    role: RoleClamp,
    acknowledged: frozenset[ClinicalObjectId],
    resolved: frozenset[ClinicalObjectId] | None = None,
) -> DecisionQueue:
    resolved = resolved or frozenset()
    candidates: list[LayoutDirective] = []
    for d in directives:
        if d.slot is AttentionSlot.HIDDEN:
            continue
        # Resolved objects are omitted from the active queue while context unchanged.
        if d.object_id in resolved:
            continue
        if d.size.value == "badge" and d.object_id is ClinicalObjectId.SOAP:
            continue  # generating SOAP excluded from queue
        if d.slot not in {
            AttentionSlot.PIN,
            AttentionSlot.PRIMARY,
            AttentionSlot.SECONDARY,
        }:
            continue
        if d.object_id in role.suppress_objects and d.priority is not PriorityLevel.P0:
            continue
        candidates.append(d)

    def sort_key(d: LayoutDirective) -> tuple:
        weight = lens_weight(lens, d.object_id)
        uncertainty_boost = 0
        if role.trust_uncertainty_boost or (
            d.trust.verification is TrustVerification.UNVERIFIED
            or (
                isinstance(d.trust.confidence, float) and d.trust.confidence < 0.6
            )
        ):
            if d.trust.primary_provenance is not TrustProvenance.PHYSICIAN_EDITED:
                uncertainty_boost = -1  # earlier within same attention band
        if d.trust.primary_provenance is TrustProvenance.PHYSICIAN_EDITED:
            uncertainty_boost = 1  # later within tier

        # Spec §6.1: priority → specialty weight → attention rank → trust → id
        return (
            _PRIORITY_RANK[d.priority],
            -weight,
            _ATTENTION_RANK.get(d.object_id, 99),
            uncertainty_boost,
            d.object_id.value,
        )

    ordered = sorted(candidates, key=sort_key)

    # Prefer attention-model order for CC first among orientation when same priority
    # Already handled via _ATTENTION_RANK

    capped = ordered[: role.queue_cap]
    items: list[DecisionQueueItem] = []
    for i, d in enumerate(capped, start=1):
        reason = _REASON_FOR.get(d.object_id, ReasonCode.DOCUMENT)
        ack = (
            d.priority is PriorityLevel.P0
            and "acknowledge_required" in d.flags
            and d.object_id not in acknowledged
        )
        items.append(
            DecisionQueueItem(
                rank=i,
                object_id=d.object_id,
                reason_code=reason,
                explanation=explanation_for(d.object_id, reason),
                acknowledge_required=ack,
            )
        )

    return DecisionQueue(items=tuple(items))
