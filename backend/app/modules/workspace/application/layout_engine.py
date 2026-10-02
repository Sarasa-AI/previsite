"""Layout Adaptation Engine — slots, sizes, pin zone, cognitive budget."""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.workspace.application.priority_engine import ObjectPriority
from app.modules.workspace.application.role_profiles import RoleClamp
from app.modules.workspace.application.signals import WorkspaceSignals
from app.modules.workspace.domain.enums import (
    AttentionSlot,
    ClinicalObjectId,
    PriorityLevel,
    SizeHint,
    TrustProvenance,
    TrustVerification,
    VisibilityReason,
)
from app.modules.workspace.domain.models import LayoutDirective, TrustDescriptor


@dataclass
class LayoutDraft:
    object_id: ClinicalObjectId
    priority: PriorityLevel
    slot: AttentionSlot
    size: SizeHint
    pinned: bool
    trust: TrustDescriptor
    flags: list[str]
    visibility_reason: VisibilityReason | None


def _default_trust(
    object_id: ClinicalObjectId,
    signals: WorkspaceSignals,
) -> TrustDescriptor:
    if object_id in signals.physician_edited_objects:
        prov = TrustProvenance.PHYSICIAN_EDITED
        ver = TrustVerification.NA
    elif object_id is ClinicalObjectId.SOAP:
        prov = TrustProvenance.AI_GENERATED
        ver = {
            "verified": TrustVerification.VERIFIED,
            "partially_verified": TrustVerification.PARTIALLY_VERIFIED,
            "unverified": TrustVerification.UNVERIFIED,
        }.get(signals.verification_status or "", TrustVerification.UNVERIFIED)
    elif object_id in {
        ClinicalObjectId.TIMELINE,
        ClinicalObjectId.CRITICAL_LABS,
        ClinicalObjectId.CONFLICTS,
        ClinicalObjectId.MISSING_DATA,
    }:
        prov = TrustProvenance.SYSTEM_DERIVED
        ver = TrustVerification.NA
    elif object_id is ClinicalObjectId.DOCUMENTS:
        prov = TrustProvenance.DOCUMENT_OCR
        ver = TrustVerification.UNVERIFIED
    elif object_id is ClinicalObjectId.STORY:
        prov = TrustProvenance.AI_GENERATED
        ver = TrustVerification.UNVERIFIED
    else:
        prov = TrustProvenance.PATIENT_REPORTED
        ver = TrustVerification.NA
    return TrustDescriptor(
        primary_provenance=prov,
        all_provenance=(prov,),
        confidence=1.0 if ver is TrustVerification.NA else 0.7,
        verification=ver,
        evidence_refs=(f"object:{object_id.value}",),
    )


def _slot_for(priority: PriorityLevel, hidden: bool) -> AttentionSlot:
    if hidden:
        return AttentionSlot.HIDDEN
    if priority is PriorityLevel.P0:
        return AttentionSlot.PIN
    if priority is PriorityLevel.P1:
        return AttentionSlot.PRIMARY
    if priority is PriorityLevel.P2:
        return AttentionSlot.SECONDARY
    return AttentionSlot.DEFERRED


# Never force-hide these objects via physician dismiss (visibility-only hide is
# still inappropriate for orientation / never-hidden catalog members).
_NEVER_DISMISS_HIDE: frozenset[ClinicalObjectId] = frozenset(
    {
        ClinicalObjectId.CHIEF_COMPLAINT,
        ClinicalObjectId.ALLERGIES,
        ClinicalObjectId.SNAPSHOT,
    }
)


def build_layout_drafts(
    priorities: dict[ClinicalObjectId, ObjectPriority],
    signals: WorkspaceSignals,
    role: RoleClamp,
    acknowledged: frozenset[ClinicalObjectId],
    dismissed: frozenset[ClinicalObjectId] | None = None,
) -> list[LayoutDraft]:
    drafts: list[LayoutDraft] = []
    dismissed = dismissed or frozenset()

    for object_id, assessment in priorities.items():
        hidden = assessment.hidden
        priority = assessment.priority
        flags = list(assessment.flags)
        visibility_reason = assessment.visibility_reason if hidden else None

        # Physician dismiss → hide with physician_dismissed (visibility only).
        # Never-hide objects and already-hidden objects are left unchanged.
        if (
            object_id in dismissed
            and not hidden
            and object_id not in _NEVER_DISMISS_HIDE
        ):
            hidden = True
            visibility_reason = VisibilityReason.PHYSICIAN_DISMISSED

        # Collapse acknowledged P0 that is no longer P0 → size handled below; if still P0 keep pin
        if object_id in acknowledged and priority is PriorityLevel.P0:
            flags = [f for f in flags if f != "acknowledge_required"]
        elif object_id in acknowledged and priority is not PriorityLevel.P0:
            # acknowledged and demoted
            pass

        slot = _slot_for(priority, hidden)
        size = SizeHint.STANDARD
        pinned = slot is AttentionSlot.PIN

        # Size rules
        if object_id is ClinicalObjectId.SNAPSHOT:
            size = SizeHint.STANDARD if role.snapshot_standard else SizeHint.COMPRESSED
        if object_id is ClinicalObjectId.MEDICATIONS and not hidden:
            if signals.medication_count > 10:
                size = SizeHint.EXPANDED
            elif signals.medication_count <= 3 and not signals.has_high_risk_med:
                size = SizeHint.COMPRESSED
        if object_id is ClinicalObjectId.TIMELINE and not hidden:
            if role.timeline_always_compressed or signals.timeline_event_count > 12:
                size = SizeHint.COMPRESSED
        if object_id is ClinicalObjectId.SOAP and not hidden:
            if signals.soap_status in {"pending", "generating"} or role.soap_deferred:
                slot = AttentionSlot.DEFERRED
                size = SizeHint.BADGE
                pinned = False
            elif signals.verification_status in {"partially_verified", "unverified"}:
                slot = AttentionSlot.PRIMARY
                size = SizeHint.EXPANDED
                pinned = False
        if object_id is ClinicalObjectId.MISSING_DATA and not hidden and priority is PriorityLevel.P0:
            slot = AttentionSlot.PIN
            size = SizeHint.EXPANDED
            pinned = True
        if object_id is ClinicalObjectId.CRITICAL_ALERTS and not hidden:
            size = SizeHint.EXPANDED
            slot = AttentionSlot.PIN
            pinned = True
        if priority is PriorityLevel.P0 and not hidden and object_id is not ClinicalObjectId.SOAP:
            slot = AttentionSlot.PIN
            pinned = True
            if size is SizeHint.STANDARD:
                size = SizeHint.EXPANDED

        # CC always pin when present
        if object_id is ClinicalObjectId.CHIEF_COMPLAINT and not hidden:
            slot = AttentionSlot.PIN
            pinned = True

        # Allergy chip pin when drug allergy documented
        if (
            object_id is ClinicalObjectId.ALLERGIES
            and signals.has_drug_allergy
            and role.pin_allergy_chip
            and not hidden
        ):
            slot = AttentionSlot.PIN
            pinned = True

        # Acknowledge-required on remaining P0
        if priority is PriorityLevel.P0 and not hidden and object_id not in acknowledged:
            if "acknowledge_required" not in flags:
                flags.append("acknowledge_required")

        # Uncertainty: cannot compress if priority >= P2 and unverified
        trust = _default_trust(object_id, signals)
        if (
            not hidden
            and size is SizeHint.COMPRESSED
            and priority in {PriorityLevel.P0, PriorityLevel.P1, PriorityLevel.P2}
            and (
                trust.verification is TrustVerification.UNVERIFIED
                or (isinstance(trust.confidence, float) and trust.confidence < 0.6)
            )
        ):
            size = SizeHint.STANDARD

        # No labs → medications expanded (spec §5.1)
        if (
            object_id is ClinicalObjectId.MEDICATIONS
            and not signals.has_labs
            and not hidden
            and size is not SizeHint.EXPANDED
        ):
            size = SizeHint.EXPANDED

        drafts.append(
            LayoutDraft(
                object_id=object_id,
                priority=priority,
                slot=slot,
                size=size,
                pinned=pinned,
                trust=trust,
                flags=flags,
                visibility_reason=visibility_reason,
            )
        )

    # Cognitive budget: max primary, max expanded (excl pin)
    primary = [d for d in drafts if d.slot is AttentionSlot.PRIMARY]
    if len(primary) > role.max_primary:
        # Defer lowest priority (P3 first, then by object_id)
        overflow = sorted(
            primary,
            key=lambda d: (_PRIORITY_ORDER[d.priority], d.object_id.value),
            reverse=True,
        )
        for d in overflow[role.max_primary :]:
            d.slot = AttentionSlot.DEFERRED
            if d.visibility_reason is None and d.slot is AttentionSlot.HIDDEN:
                pass

    expanded = [
        d
        for d in drafts
        if d.size is SizeHint.EXPANDED and d.slot is not AttentionSlot.PIN and not d.pinned
    ]
    if len(expanded) > role.max_expanded:
        overflow = sorted(
            expanded,
            key=lambda d: (_PRIORITY_ORDER[d.priority], d.object_id.value),
            reverse=True,
        )
        for d in overflow[role.max_expanded :]:
            d.size = SizeHint.STANDARD

    return drafts


_PRIORITY_ORDER = {
    PriorityLevel.P0: 0,
    PriorityLevel.P1: 1,
    PriorityLevel.P2: 2,
    PriorityLevel.P3: 3,
}


def apply_cognitive_budget_visibility(
    drafts: list[LayoutDraft],
) -> list[LayoutDraft]:
    """Mark deferred overflow with cognitive_budget reason only when hidden."""
    # Spec: overflow assigned deferred, not hidden — no visibility_reason change
    return drafts


def to_directives(drafts: list[LayoutDraft]) -> tuple[LayoutDirective, ...]:
    # Stable catalog order for determinism
    order = {oid: i for i, oid in enumerate(ClinicalObjectId)}
    sorted_drafts = sorted(drafts, key=lambda d: order[d.object_id])
    return tuple(
        LayoutDirective(
            object_id=d.object_id,
            priority=d.priority,
            slot=d.slot,
            size=d.size,
            pinned=d.pinned,
            trust=d.trust,
            flags=tuple(d.flags),
            visibility_reason=d.visibility_reason,
        )
        for d in sorted_drafts
    )


def build_pin_zone(
    directives: tuple[LayoutDirective, ...],
    signals: WorkspaceSignals,
    role: RoleClamp,
) -> tuple[ClinicalObjectId, ...]:
    pins: list[ClinicalObjectId] = []
    by_id = {d.object_id: d for d in directives}

    if ClinicalObjectId.CHIEF_COMPLAINT in by_id and by_id[
        ClinicalObjectId.CHIEF_COMPLAINT
    ].slot is AttentionSlot.PIN:
        pins.append(ClinicalObjectId.CHIEF_COMPLAINT)

    p0s = [
        d.object_id
        for d in directives
        if d.priority is PriorityLevel.P0
        and d.slot is AttentionSlot.PIN
        and d.object_id not in pins
    ]
    # Safety order
    tie = [
        ClinicalObjectId.CONFLICTS,
        ClinicalObjectId.ALLERGIES,
        ClinicalObjectId.RED_FLAGS,
        ClinicalObjectId.CRITICAL_LABS,
        ClinicalObjectId.MISSING_DATA,
        ClinicalObjectId.CRITICAL_ALERTS,
    ]
    ordered_p0 = [oid for oid in tie if oid in p0s]
    ordered_p0.extend(oid for oid in sorted(p0s, key=lambda x: x.value) if oid not in ordered_p0)
    pins.extend(ordered_p0[: 3 if ClinicalObjectId.CHIEF_COMPLAINT in pins else 3])

    if (
        role.pin_allergy_chip
        and signals.has_drug_allergy
        and ClinicalObjectId.ALLERGIES not in pins
        and ClinicalObjectId.ALLERGIES in by_id
        and by_id[ClinicalObjectId.ALLERGIES].slot is AttentionSlot.PIN
    ):
        pins.append(ClinicalObjectId.ALLERGIES)

    # Ensure every pin_zone entry has pinned+pin on directive — already required
    return tuple(dict.fromkeys(pins))  # preserve order, unique
