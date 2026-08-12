"""Pure signal extraction from ClinicalContext + adapter inputs (read-only)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.modules.workspace.application.inputs import (
    OrchestratorInputs,
    SessionState,
    ValidatedConflict,
)
from app.modules.workspace.domain.enums import ClinicalObjectId
from app.schemas.clinical_context import ClinicalContext

_SAFETY_KEYWORDS = frozenset(
    {
        "chest pain",
        "shortness of breath",
        "sob",
        "syncope",
        "stroke",
        "anaphylaxis",
        "suicidal",
        "hemorrhage",
        "bleeding",
        "seizure",
        "unconscious",
        "critical",
        "urgent",
        "stat",
        "panic",
    }
)

_ALLERGY_CC_KEYWORDS = frozenset({"allergy", "allergic", "rash", "anaphylaxis"})

_HIGH_RISK_MED_TOKENS = frozenset(
    {
        "warfarin",
        "heparin",
        "insulin",
        "methotrexate",
        "digoxin",
        "amiodarone",
        "lithium",
        "opio",
        "fentanyl",
        "morphine",
        "oxycodone",
    }
)

_CRITICAL_FLAG_RE = re.compile(
    r"\b(critical|panic|hh|ll|\*\*\*)\b", re.IGNORECASE
)
_K_RE = re.compile(r"\b(?:k|potassium)\b[^0-9\-]*(-?\d+(?:\.\d+)?)", re.I)
_NA_RE = re.compile(r"\b(?:na|sodium)\b[^0-9\-]*(-?\d+(?:\.\d+)?)", re.I)
_GLU_RE = re.compile(r"\b(?:glu|glucose)\b[^0-9\-]*(-?\d+(?:\.\d+)?)", re.I)
_HGB_RE = re.compile(r"\b(?:hgb|hemoglobin|hb)\b[^0-9\-]*(-?\d+(?:\.\d+)?)", re.I)
_INR_RE = re.compile(r"\binr\b[^0-9\-]*(-?\d+(?:\.\d+)?)", re.I)
_TROP_RE = re.compile(r"\btroponin\b", re.I)


@dataclass(frozen=True)
class WorkspaceSignals:
    """Derived presence/urgency signals — orchestration only, no clinical diagnosis."""

    chief_complaint: str | None
    has_chief_complaint: bool
    red_flags: tuple[str, ...]
    acute_presentation: bool
    red_flag_safety_keyword: bool
    validated_conflicts: tuple[ValidatedConflict, ...]
    has_high_confidence_conflict: bool
    allergy_text: str
    has_allergy_documented: bool
    has_drug_allergy: bool
    allergies_status_unknown: bool
    medication_names: tuple[str, ...]
    medication_count: int
    has_high_risk_med: bool
    allergy_med_interaction: bool
    lab_texts: tuple[str, ...]
    has_labs: bool
    has_critical_labs: bool
    timeline_event_count: int
    unknown_chronology_count: int
    acute_onset_under_72h: bool
    document_count: int
    patient_questions: tuple[str, ...]
    patient_question_safety: bool
    chronic_condition_count: int
    has_pmh_content: bool
    surgical_history: str
    soap_status: str
    verification_status: str | None
    soap_exists: bool
    offline: bool
    session_locked: bool
    soap_accepted: bool
    physician_edited_objects: frozenset[ClinicalObjectId] = field(
        default_factory=frozenset
    )


def _parse_float(match: re.Match[str] | None) -> float | None:
    if match is None:
        return None
    try:
        return float(match.group(1))
    except (TypeError, ValueError):
        return None


def _lab_is_critical(text: str) -> bool:
    if not text or not text.strip():
        return False
    if _CRITICAL_FLAG_RE.search(text):
        return True
    k = _parse_float(_K_RE.search(text))
    if k is not None and (k < 2.5 or k > 6.0):
        return True
    na = _parse_float(_NA_RE.search(text))
    if na is not None and (na < 120 or na > 160):
        return True
    glu = _parse_float(_GLU_RE.search(text))
    if glu is not None and (glu < 50 or glu > 400):
        return True
    hgb = _parse_float(_HGB_RE.search(text))
    if hgb is not None and hgb < 7.0:
        return True
    inr = _parse_float(_INR_RE.search(text))
    if inr is not None and inr > 5.0:
        return True
    if _TROP_RE.search(text) and re.search(
        r"\b(elevated|high|positive|abnormal)\b", text, re.I
    ):
        return True
    return False


def _contains_any(text: str, keywords: frozenset[str]) -> bool:
    lowered = text.lower()
    return any(k in lowered for k in keywords)


def extract_signals(
    context: ClinicalContext,
    session_state: SessionState,
    inputs: OrchestratorInputs,
) -> WorkspaceSignals:
    summary = context.summary
    overview = context.overview

    cc = (summary.chief_complaint or "").strip() or None
    has_cc = bool(cc)

    # Clinical Intelligence findings (adapter inputs) fold into existing signal paths.
    finding_red_flags = tuple(
        s.title.strip()
        for s in inputs.clinical_findings
        if s.is_red_flag and s.title and s.title.strip()
    )
    merged_red: list[str] = []
    seen_rf: set[str] = set()
    for flag in (
        *(f.strip() for f in inputs.red_flags if f and f.strip()),
        *finding_red_flags,
    ):
        key = flag.lower()
        if key not in seen_rf:
            seen_rf.add(key)
            merged_red.append(flag)
    red_flags = tuple(merged_red)

    finding_conflicts = tuple(
        ValidatedConflict(
            concept=s.title.strip(),
            confidence="high" if s.confidence == "high" else "low",
            involves_medication=False,
        )
        for s in inputs.clinical_findings
        if s.is_conflict and s.title and s.title.strip()
    )
    acute = False
    if summary.symptom_duration:
        duration = summary.symptom_duration.lower()
        if any(tok in duration for tok in ("hour", "day", "acute", "sudden")):
            acute = True
        if re.search(r"\b([1-2])\s*day", duration):
            acute = True
    if summary.symptom_onset and _contains_any(
        summary.symptom_onset, frozenset({"sudden", "acute", "today", "yesterday"})
    ):
        acute = True
    if cc and _contains_any(cc, frozenset({"sudden", "acute", "severe"})):
        acute = True

    red_safety = any(_contains_any(f, _SAFETY_KEYWORDS) for f in red_flags)

    conflicts = (*inputs.validated_conflicts, *finding_conflicts)
    high_conf = any(c.confidence == "high" for c in conflicts)

    allergy_text = ""
    if overview and overview.allergies.strip():
        allergy_text = overview.allergies.strip()
    elif summary.allergies:
        allergy_text = ", ".join(a for a in summary.allergies if a).strip()
    has_allergy = bool(allergy_text) and allergy_text.lower() not in {
        "nkda",
        "none",
        "n/a",
        "na",
        "no known allergies",
        "no known drug allergies",
    }
    # Treat documented non-empty allergy text as drug allergy unless explicitly NKDA
    has_drug_allergy = has_allergy

    med_names: list[str] = []
    if overview and overview.current_medications:
        med_names.extend(m.name for m in overview.current_medications if m.name.strip())
    if context.medication_evidence:
        med_names.extend(m.name for m in context.medication_evidence if m.name.strip())
    if summary.current_medications:
        med_names.extend(m for m in summary.current_medications if m and m.strip())
    # Stable unique order
    seen: set[str] = set()
    unique_meds: list[str] = []
    for name in med_names:
        key = name.strip().lower()
        if key and key not in seen:
            seen.add(key)
            unique_meds.append(name.strip())
    medication_names = tuple(unique_meds)
    has_high_risk = any(
        any(tok in name.lower() for tok in _HIGH_RISK_MED_TOKENS)
        for name in medication_names
    )
    allergy_med = bool(
        has_drug_allergy
        and medication_names
        and (
            any(c.involves_medication for c in conflicts)
            or (cc is not None and _contains_any(cc, _ALLERGY_CC_KEYWORDS))
        )
    )
    # Also promote allergy–med when both drug allergy and meds present (spec P0 path)
    allergy_med_interaction = allergy_med or (
        has_drug_allergy and bool(medication_names)
    )

    lab_texts: list[str] = []
    for lab in context.lab_evidence:
        if lab.extracted_data:
            lab_texts.append(lab.extracted_data)
        elif lab.name:
            lab_texts.append(lab.name)
    if overview:
        for lab in overview.lab_results:
            if lab.extracted_data:
                lab_texts.append(lab.extracted_data)
            elif lab.name:
                lab_texts.append(lab.name)
    has_labs = bool(lab_texts) or bool(context.lab_evidence) or bool(
        overview and overview.lab_results
    )
    has_critical = any(_lab_is_critical(t) for t in lab_texts)

    timeline = context.timeline
    event_count = len(timeline.events) if timeline else 0
    unknown_count = len(timeline.unknown_chronology) if timeline else 0
    acute_72 = False
    if timeline:
        for event in timeline.events:
            if event.temporal.relative_unit == "days" and event.temporal.relative_value is not None:
                if event.temporal.relative_value < 3:
                    acute_72 = True
            if event.temporal.relative_unit == "hours" and event.temporal.relative_value is not None:
                acute_72 = True
            if event.temporal.kind.value in {"today", "yesterday"}:
                acute_72 = True

    questions = tuple(q.strip() for q in inputs.patient_questions if q and q.strip())
    if not questions and overview and overview.patient_questions:
        questions = (overview.patient_questions.strip(),)
    q_safety = any(_contains_any(q, _SAFETY_KEYWORDS) for q in questions)

    chronic_count = len(overview.chronic_conditions) if overview else 0
    if summary.past_medical_history:
        chronic_count = max(chronic_count, len(summary.past_medical_history))
    surgical = (overview.surgical_history.strip() if overview else "") or ""
    has_pmh = bool(
        chronic_count
        or surgical
        or (overview and overview.family_history.strip())
        or context.pmh_assertions
        or (summary.past_medical_history)
    )

    return WorkspaceSignals(
        chief_complaint=cc,
        has_chief_complaint=has_cc,
        red_flags=red_flags,
        acute_presentation=acute,
        red_flag_safety_keyword=red_safety,
        validated_conflicts=conflicts,
        has_high_confidence_conflict=high_conf,
        allergy_text=allergy_text,
        has_allergy_documented=has_allergy,
        has_drug_allergy=has_drug_allergy,
        allergies_status_unknown=inputs.allergies_status_unknown,
        medication_names=medication_names,
        medication_count=len(medication_names),
        has_high_risk_med=has_high_risk,
        allergy_med_interaction=allergy_med_interaction,
        lab_texts=tuple(lab_texts),
        has_labs=has_labs,
        has_critical_labs=has_critical,
        timeline_event_count=event_count,
        unknown_chronology_count=unknown_count,
        acute_onset_under_72h=acute_72,
        document_count=inputs.document_count or len(context.file_analyses),
        patient_questions=questions,
        patient_question_safety=q_safety,
        chronic_condition_count=chronic_count,
        has_pmh_content=has_pmh,
        surgical_history=surgical,
        soap_status=session_state.soap_status,
        verification_status=session_state.verification_status,
        soap_exists=session_state.soap_exists
        or session_state.soap_status in {"ready", "generating", "failed"},
        offline=session_state.offline,
        session_locked=session_state.session_locked,
        soap_accepted=session_state.soap_accepted,
        physician_edited_objects=inputs.physician_edited_objects,
    )
