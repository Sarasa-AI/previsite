"""Specialty lens weights — queue order / size promotion only; never hides P0."""

from __future__ import annotations

from app.modules.workspace.domain.enums import ClinicalObjectId, SpecialtyLens

_DEFAULT = 1.0

_LENS_WEIGHTS: dict[SpecialtyLens, dict[ClinicalObjectId, float]] = {
    SpecialtyLens.GENERAL_MEDICINE: {},
    SpecialtyLens.ENDOCRINOLOGY: {
        ClinicalObjectId.LABS: 1.5,
        ClinicalObjectId.CRITICAL_LABS: 1.5,
        ClinicalObjectId.MEDICATIONS: 1.3,
        ClinicalObjectId.TIMELINE: 1.4,
    },
    SpecialtyLens.CARDIOLOGY: {
        ClinicalObjectId.RED_FLAGS: 1.5,
        ClinicalObjectId.TIMELINE: 1.4,
        ClinicalObjectId.MEDICATIONS: 1.3,
        ClinicalObjectId.DOCUMENTS: 1.2,
    },
    SpecialtyLens.NEUROLOGY: {
        ClinicalObjectId.RED_FLAGS: 1.5,
        ClinicalObjectId.TIMELINE: 1.4,
        ClinicalObjectId.PATIENT_QUESTIONS: 1.2,
        ClinicalObjectId.LABS: 0.9,
    },
    SpecialtyLens.FAMILY_MEDICINE: {
        ClinicalObjectId.PATIENT_QUESTIONS: 1.3,
        ClinicalObjectId.PMH: 1.2,
        ClinicalObjectId.MEDICATIONS: 1.2,
        ClinicalObjectId.SOAP: 1.1,
    },
}


def lens_weight(lens: SpecialtyLens, object_id: ClinicalObjectId) -> float:
    return _LENS_WEIGHTS.get(lens, {}).get(object_id, _DEFAULT)
