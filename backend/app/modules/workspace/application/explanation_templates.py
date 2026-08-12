"""Deterministic Decision Queue explanation templates (no clinical recommendations)."""

from __future__ import annotations

from app.modules.workspace.domain.enums import ClinicalObjectId, ReasonCode

_TEMPLATES: dict[tuple[ClinicalObjectId, ReasonCode], str] = {
    (ClinicalObjectId.CHIEF_COMPLAINT, ReasonCode.ORIENT): (
        "Chief complaint orients the visit before other clinical detail."
    ),
    (ClinicalObjectId.CONFLICTS, ReasonCode.SAFETY): (
        "Validated clinical conflicts require review before proceeding."
    ),
    (ClinicalObjectId.ALLERGIES, ReasonCode.SAFETY): (
        "Documented allergies are safety-critical for medication decisions."
    ),
    (ClinicalObjectId.RED_FLAGS, ReasonCode.SAFETY): (
        "Red flags are safety signals that must be reviewed early."
    ),
    (ClinicalObjectId.CRITICAL_LABS, ReasonCode.SAFETY): (
        "Critical lab markers outrank routine documentation."
    ),
    (ClinicalObjectId.CRITICAL_ALERTS, ReasonCode.SAFETY): (
        "Critical alert band aggregates active safety signals."
    ),
    (ClinicalObjectId.MISSING_DATA, ReasonCode.SAFETY): (
        "Required safety intake fields are missing and must be addressed."
    ),
    (ClinicalObjectId.MISSING_DATA, ReasonCode.OPEN_LOOP): (
        "Missing information leaves an open clinical loop."
    ),
    (ClinicalObjectId.STORY, ReasonCode.ORIENT): (
        "Clinical story provides visit orientation from evidence-bound narrative."
    ),
    (ClinicalObjectId.TIMELINE, ReasonCode.EVIDENCE): (
        "Timeline provides chronological evidence for the visit."
    ),
    (ClinicalObjectId.LABS, ReasonCode.EVIDENCE): (
        "Laboratory evidence informs objective clinical review."
    ),
    (ClinicalObjectId.MEDICATIONS, ReasonCode.EVIDENCE): (
        "Medication list is objective structured data for review."
    ),
    (ClinicalObjectId.PATIENT_QUESTIONS, ReasonCode.OPEN_LOOP): (
        "Unanswered patient questions are open loops before documentation."
    ),
    (ClinicalObjectId.SOAP, ReasonCode.DOCUMENT): (
        "SOAP documentation is confirmatory and follows clinical appraisal."
    ),
    (ClinicalObjectId.DOCUMENTS, ReasonCode.DOCUMENT): (
        "Uploaded documents are reference material for on-demand review."
    ),
    (ClinicalObjectId.PMH, ReasonCode.DOCUMENT): (
        "Past medical history is deferred reference detail."
    ),
    (ClinicalObjectId.SNAPSHOT, ReasonCode.DOCUMENT): (
        "Visit snapshot holds demographics and metadata."
    ),
}


def explanation_for(object_id: ClinicalObjectId, reason_code: ReasonCode) -> str:
    key = (object_id, reason_code)
    if key in _TEMPLATES:
        return _TEMPLATES[key]
    return (
        f"{object_id.value} ranked for review under {reason_code.value} "
        f"attention category."
    )
