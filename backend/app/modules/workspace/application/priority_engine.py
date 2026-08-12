"""Clinical Priority Engine — deterministic per-object priority (no diagnosis)."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.modules.workspace.application.role_profiles import RoleClamp
from app.modules.workspace.application.signals import WorkspaceSignals
from app.modules.workspace.domain.enums import (
    ClinicalObjectId,
    PriorityLevel,
    VisibilityReason,
)
from app.modules.workspace.domain.models import DecisionTraceStep

# Safety P0 tie-break (spec §3.3): conflicts > allergies > red_flags > critical_labs > missing_data
_P0_TIEBREAK: tuple[ClinicalObjectId, ...] = (
    ClinicalObjectId.CONFLICTS,
    ClinicalObjectId.ALLERGIES,
    ClinicalObjectId.RED_FLAGS,
    ClinicalObjectId.CRITICAL_LABS,
    ClinicalObjectId.MISSING_DATA,
)

_PRIORITY_RANK = {
    PriorityLevel.P0: 0,
    PriorityLevel.P1: 1,
    PriorityLevel.P2: 2,
    PriorityLevel.P3: 3,
}


@dataclass
class ObjectPriority:
    object_id: ClinicalObjectId
    priority: PriorityLevel
    present: bool
    hidden: bool
    visibility_reason: VisibilityReason | None = None
    flags: list[str] = field(default_factory=list)
    trace_steps: list[DecisionTraceStep] = field(default_factory=list)


def _step(
    object_id: ClinicalObjectId,
    label: str,
    before: PriorityLevel | None,
    after: PriorityLevel,
    detail: str,
) -> DecisionTraceStep:
    return DecisionTraceStep(
        object_id=object_id,
        step_label=label,
        priority_before=before,
        priority_after=after,
        detail=detail,
    )


def _set_priority(
    assessment: ObjectPriority,
    new_priority: PriorityLevel,
    label: str,
    detail: str,
) -> None:
    before = assessment.priority
    if before is new_priority and assessment.trace_steps:
        return
    assessment.priority = new_priority
    assessment.trace_steps.append(
        _step(assessment.object_id, label, before, new_priority, detail)
    )


def compute_base_priorities(
    signals: WorkspaceSignals,
    role: RoleClamp,
) -> dict[ClinicalObjectId, ObjectPriority]:
    """Compute base priority / presence for every catalog object."""
    out: dict[ClinicalObjectId, ObjectPriority] = {}

    # chief_complaint
    cc = ObjectPriority(
        ClinicalObjectId.CHIEF_COMPLAINT, PriorityLevel.P1, present=signals.has_chief_complaint, hidden=False
    )
    if signals.has_chief_complaint:
        _set_priority(cc, PriorityLevel.P1, "base_priority", "Chief complaint present → P1")
        cc.hidden = False
    else:
        cc.present = False
        cc.hidden = True
        cc.visibility_reason = VisibilityReason.NO_DATA
        _set_priority(cc, PriorityLevel.P3, "base_priority", "Chief complaint absent → routed via missing_data")
    out[cc.object_id] = cc

    # red_flags
    rf = ObjectPriority(
        ClinicalObjectId.RED_FLAGS, PriorityLevel.P1, present=bool(signals.red_flags), hidden=False
    )
    if not signals.red_flags:
        rf.hidden = True
        rf.visibility_reason = VisibilityReason.NO_DATA
        _set_priority(rf, PriorityLevel.P3, "base_priority", "No red flags → hidden")
    else:
        _set_priority(rf, PriorityLevel.P1, "base_priority", "Red flags present → P1")
        if signals.acute_presentation or signals.red_flag_safety_keyword:
            _set_priority(
                rf,
                PriorityLevel.P0,
                "promote",
                "Red flags with acute/safety keyword → P0",
            )
        if role.red_flags_boost > 1.0 and rf.priority is not PriorityLevel.P0:
            # Boost is queue weight; Emergency also multiplies priority emphasis via weight only
            pass
    out[rf.object_id] = rf

    # conflicts
    cf = ObjectPriority(
        ClinicalObjectId.CONFLICTS,
        PriorityLevel.P1,
        present=bool(signals.validated_conflicts),
        hidden=False,
    )
    if not signals.validated_conflicts:
        cf.hidden = True
        cf.visibility_reason = VisibilityReason.NO_DATA
        _set_priority(cf, PriorityLevel.P3, "base_priority", "No validated conflicts → hidden")
    else:
        _set_priority(cf, PriorityLevel.P1, "base_priority", "Validated conflicts present → P1")
        if signals.has_high_confidence_conflict:
            _set_priority(
                cf, PriorityLevel.P0, "promote", "High-confidence validated conflict → P0"
            )
    out[cf.object_id] = cf

    # allergies — never hidden
    al = ObjectPriority(
        ClinicalObjectId.ALLERGIES,
        PriorityLevel.P1,
        present=True,
        hidden=False,
    )
    if signals.has_allergy_documented:
        _set_priority(al, PriorityLevel.P1, "base_priority", "Allergy documented → P1")
        if signals.has_drug_allergy and (
            signals.medication_count > 0
            or (
                signals.chief_complaint
                and any(
                    k in signals.chief_complaint.lower()
                    for k in ("allergy", "allergic", "rash", "anaphylaxis")
                )
            )
        ):
            _set_priority(
                al,
                PriorityLevel.P0,
                "promote",
                "Drug allergy with meds or CC allergy keyword → P0",
            )
    else:
        _set_priority(
            al, PriorityLevel.P3, "demote", "No allergies documented → P3 (not hidden)"
        )
    out[al.object_id] = al

    # critical_labs
    cl = ObjectPriority(
        ClinicalObjectId.CRITICAL_LABS,
        PriorityLevel.P0,
        present=signals.has_critical_labs,
        hidden=False,
    )
    if not signals.has_labs:
        cl.hidden = True
        cl.present = False
        cl.visibility_reason = VisibilityReason.NO_DATA
        _set_priority(cl, PriorityLevel.P3, "base_priority", "No labs → critical_labs hidden")
    elif signals.has_critical_labs:
        _set_priority(cl, PriorityLevel.P0, "promote", "Critical lab marker detected → P0")
    else:
        cl.hidden = True
        cl.visibility_reason = VisibilityReason.NO_DATA
        _set_priority(
            cl, PriorityLevel.P2, "base_priority", "Labs present but none critical → hide critical_labs"
        )
    out[cl.object_id] = cl

    # labs
    labs = ObjectPriority(
        ClinicalObjectId.LABS, PriorityLevel.P2, present=signals.has_labs, hidden=False
    )
    if not signals.has_labs:
        labs.hidden = True
        labs.visibility_reason = VisibilityReason.NO_DATA
        _set_priority(labs, PriorityLevel.P3, "base_priority", "No labs → hidden")
    else:
        _set_priority(labs, PriorityLevel.P2, "base_priority", "Labs present → P2")
        if signals.has_critical_labs:
            _set_priority(labs, PriorityLevel.P1, "promote", "Critical labs active → labs P1")
    out[labs.object_id] = labs

    # medications
    meds = ObjectPriority(
        ClinicalObjectId.MEDICATIONS,
        PriorityLevel.P2,
        present=signals.medication_count > 0,
        hidden=False,
    )
    if signals.medication_count == 0:
        meds.hidden = True
        meds.visibility_reason = VisibilityReason.NO_DATA
        _set_priority(meds, PriorityLevel.P3, "base_priority", "No medications → hidden")
    else:
        _set_priority(meds, PriorityLevel.P2, "base_priority", "Medications present → P2")
        if (
            signals.has_high_risk_med
            or signals.allergy_med_interaction
            or any(c.involves_medication for c in signals.validated_conflicts)
        ):
            _set_priority(
                meds, PriorityLevel.P1, "promote", "High-risk med / allergy–med / conflict → P1"
            )
    out[meds.object_id] = meds

    # timeline
    tl = ObjectPriority(
        ClinicalObjectId.TIMELINE,
        PriorityLevel.P2,
        present=signals.timeline_event_count > 0,
        hidden=False,
    )
    if signals.timeline_event_count == 0:
        tl.hidden = True
        tl.visibility_reason = VisibilityReason.NO_DATA
        _set_priority(tl, PriorityLevel.P3, "base_priority", "Empty timeline → hidden")
    else:
        _set_priority(tl, PriorityLevel.P2, "base_priority", "Timeline events present → P2")
        if signals.acute_onset_under_72h or signals.unknown_chronology_count > 2:
            _set_priority(
                tl,
                PriorityLevel.P1,
                "promote",
                "Acute onset <72h or unknown chronology >2 → P1",
            )
        if signals.timeline_event_count > 12:
            tl.flags.append("show_progression_only")
    out[tl.object_id] = tl

    # soap
    soap = ObjectPriority(
        ClinicalObjectId.SOAP, PriorityLevel.P2, present=signals.soap_exists, hidden=False
    )
    if not signals.soap_exists:
        soap.hidden = True
        soap.visibility_reason = VisibilityReason.NO_DATA
        _set_priority(soap, PriorityLevel.P3, "base_priority", "No SOAP → hidden")
    elif signals.soap_status in {"pending", "generating"}:
        _set_priority(soap, PriorityLevel.P2, "base_priority", "SOAP generating → deferred badge")
    elif signals.soap_status == "failed":
        _set_priority(soap, PriorityLevel.P2, "base_priority", "SOAP failed → P2 acknowledge")
        soap.flags.append("acknowledge_required")
    else:
        _set_priority(soap, PriorityLevel.P2, "base_priority", "SOAP ready → P2")
        if signals.verification_status in {"partially_verified", "unverified"} or bool(
            signals.validated_conflicts
        ):
            _set_priority(
                soap, PriorityLevel.P1, "promote", "Unverified SOAP or conflicts → P1"
            )
    if role.soap_deferred and not soap.hidden:
        # Nurse/Emergency: keep present but will be deferred in layout
        pass
    out[soap.object_id] = soap

    # documents
    docs = ObjectPriority(
        ClinicalObjectId.DOCUMENTS,
        PriorityLevel.P3,
        present=signals.document_count > 0,
        hidden=False,
    )
    if signals.document_count == 0:
        docs.hidden = True
        docs.visibility_reason = VisibilityReason.NO_DATA
        _set_priority(docs, PriorityLevel.P3, "base_priority", "No documents → hidden")
    else:
        _set_priority(docs, PriorityLevel.P3, "base_priority", "Documents present → P3")
        if role.elevate_documents:
            _set_priority(docs, PriorityLevel.P2, "role_clamp", "Telehealth elevates documents → P2")
    out[docs.object_id] = docs

    # snapshot — never hidden
    snap = ObjectPriority(
        ClinicalObjectId.SNAPSHOT, PriorityLevel.P3, present=True, hidden=False
    )
    _set_priority(snap, PriorityLevel.P3, "base_priority", "Snapshot always present → P3")
    if role.snapshot_standard:
        _set_priority(snap, PriorityLevel.P2, "role_clamp", "Telehealth snapshot → P2")
    out[snap.object_id] = snap

    # story — presence decided later by story engine; start hidden
    story = ObjectPriority(
        ClinicalObjectId.STORY, PriorityLevel.P2, present=False, hidden=True
    )
    story.visibility_reason = VisibilityReason.NO_DATA
    _set_priority(story, PriorityLevel.P2, "base_priority", "Story pending generation gate")
    if not role.story_enabled:
        story.hidden = True
        story.visibility_reason = VisibilityReason.SPECIALTY_FILTER
        _set_priority(
            story, PriorityLevel.P3, "role_clamp", "Role disables story → hidden"
        )
    out[story.object_id] = story

    # missing_data
    missing = ObjectPriority(
        ClinicalObjectId.MISSING_DATA, PriorityLevel.P3, present=False, hidden=True
    )
    missing.visibility_reason = VisibilityReason.NO_DATA
    _set_priority(missing, PriorityLevel.P3, "base_priority", "Missing data default hidden")
    needs_missing = (
        not signals.has_chief_complaint
        or signals.allergies_status_unknown
    )
    if needs_missing:
        missing.present = True
        missing.hidden = False
        missing.visibility_reason = None
        _set_priority(
            missing,
            PriorityLevel.P0,
            "promote",
            "Required field absent (CC or allergies unknown) → P0",
        )
        if role.elevate_missing_data and missing.priority is not PriorityLevel.P0:
            pass
    out[missing.object_id] = missing

    # pmh — empty → compressed (not hidden)
    pmh = ObjectPriority(
        ClinicalObjectId.PMH, PriorityLevel.P3, present=True, hidden=False
    )
    _set_priority(pmh, PriorityLevel.P3, "base_priority", "PMH default P3")
    if signals.chronic_condition_count > 3 or (
        signals.surgical_history
        and signals.chief_complaint
        and any(
            tok in signals.surgical_history.lower()
            for tok in signals.chief_complaint.lower().split()
            if len(tok) > 3
        )
    ):
        _set_priority(
            pmh, PriorityLevel.P2, "promote", "Dense PMH or surgical relevance → P2"
        )
    out[pmh.object_id] = pmh

    # patient_questions
    pq = ObjectPriority(
        ClinicalObjectId.PATIENT_QUESTIONS,
        PriorityLevel.P2,
        present=bool(signals.patient_questions),
        hidden=False,
    )
    if not signals.patient_questions:
        pq.hidden = True
        pq.visibility_reason = VisibilityReason.NO_DATA
        _set_priority(pq, PriorityLevel.P3, "base_priority", "No patient questions → hidden")
    else:
        _set_priority(pq, PriorityLevel.P2, "base_priority", "Patient questions present → P2")
        if signals.patient_question_safety:
            _set_priority(
                pq, PriorityLevel.P1, "promote", "Safety keyword in patient question → P1"
            )
    out[pq.object_id] = pq

    # critical_alerts composite band — hidden when constituent cards carry the signal
    constituents_visible = any(
        not out[oid].hidden
        for oid in (
            ClinicalObjectId.CONFLICTS,
            ClinicalObjectId.ALLERGIES,
            ClinicalObjectId.RED_FLAGS,
            ClinicalObjectId.CRITICAL_LABS,
        )
        if oid in out
    )
    ca = ObjectPriority(
        ClinicalObjectId.CRITICAL_ALERTS,
        PriorityLevel.P3,
        present=False,
        hidden=True,
    )
    ca.visibility_reason = VisibilityReason.NO_DATA
    if constituents_visible:
        _set_priority(
            ca,
            PriorityLevel.P3,
            "base_priority",
            "Critical alerts band deferred to constituent safety cards",
        )
        ca.visibility_reason = VisibilityReason.DEPENDENCY_UNAVAILABLE
    else:
        _set_priority(ca, PriorityLevel.P3, "base_priority", "No safety signals → alerts hidden")
    out[ca.object_id] = ca

    # Physician edit lock: cannot demote below P2
    for oid in signals.physician_edited_objects:
        if oid in out and not out[oid].hidden:
            if _PRIORITY_RANK[out[oid].priority] > _PRIORITY_RANK[PriorityLevel.P2]:
                _set_priority(
                    out[oid],
                    PriorityLevel.P2,
                    "edit_lock",
                    "Physician-edited object cannot demote below P2",
                )

    # Cap visible P0 at 3 (safety tie-break order)
    all_p0 = [
        oid
        for oid, a in out.items()
        if not a.hidden and a.priority is PriorityLevel.P0
    ]

    def _p0_rank(oid: ClinicalObjectId) -> int:
        try:
            return _P0_TIEBREAK.index(oid)
        except ValueError:
            return 100

    all_p0_sorted = sorted(all_p0, key=_p0_rank)
    if len(all_p0_sorted) > 3:
        for oid in all_p0_sorted[3:]:
            _set_priority(
                out[oid],
                PriorityLevel.P1,
                "p0_cap",
                "Exceeds max 3 P0 — demote by safety tie-break",
            )

    # Role suppress (never P0 safety)
    for oid in role.suppress_objects:
        if oid in out and out[oid].priority is not PriorityLevel.P0:
            out[oid].hidden = True
            out[oid].visibility_reason = VisibilityReason.SPECIALTY_FILTER
            _set_priority(
                out[oid],
                PriorityLevel.P3,
                "role_clamp",
                "Role suppresses object from workspace",
            )

    return out
