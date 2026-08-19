"""Pure signal derivation from ClinicalContext for orchestration inputs.

`OrchestratorInputs` carries facts that are not first-class fields on
`ClinicalContext`. Two of them — red flags and patient questions — are recorded by
the intake LLM into the ClinicalSummary and reach the aggregate folded into
``summary.additional_notes``.

Both the WorkspacePlan (via `extract_signals`) and the clinical-content projection
must read them from the *same* place, or the plan hides a card whose body content
exists — which is exactly the defect this module removes. Keep this the single
parser for those lines.
"""

from __future__ import annotations

import re

from app.schemas.clinical_context import ClinicalContext

_RED_FLAGS_LINE_RE = re.compile(r"^Red flags:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
_PATIENT_QUESTIONS_LINE_RE = re.compile(
    r"^Patient questions:\s*(.+)$", re.IGNORECASE | re.MULTILINE
)

#: Values that explicitly document "no known allergies" rather than leaving it blank.
_ALLERGY_NEGATIONS = frozenset(
    {
        "nkda",
        "none",
        "n/a",
        "na",
        "no known allergies",
        "no known drug allergies",
        "هیچ",
        "ندارد",
        "بدون حساسیت",
    }
)


def _split_semicolon_list(raw: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in raw.split(";") if part.strip())


def parse_red_flags(notes: str | None) -> tuple[str, ...]:
    """Extract the red-flag list from a rendered additional-notes block."""
    if not notes:
        return ()
    match = _RED_FLAGS_LINE_RE.search(notes)
    if not match:
        return ()
    return _split_semicolon_list(match.group(1).strip())


def parse_patient_questions(notes: str | None) -> tuple[str, ...]:
    """Extract the patient-question list from a rendered additional-notes block."""
    if not notes:
        return ()
    match = _PATIENT_QUESTIONS_LINE_RE.search(notes)
    if not match:
        return ()
    return _split_semicolon_list(match.group(1).strip())


def red_flags_from_context(context: ClinicalContext) -> tuple[str, ...]:
    """Red flags recorded for this session, deduplicated case-insensitively."""
    flags = parse_red_flags(context.summary.additional_notes)
    seen: set[str] = set()
    unique: list[str] = []
    for flag in flags:
        key = flag.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(flag)
    return tuple(unique)


def patient_questions_from_context(context: ClinicalContext) -> tuple[str, ...]:
    """Patient questions from notes, falling back to the intake overview field."""
    questions = parse_patient_questions(context.summary.additional_notes)
    if questions:
        return questions
    overview = context.overview
    if overview and overview.patient_questions.strip():
        return (overview.patient_questions.strip(),)
    return ()


def allergy_text_from_context(context: ClinicalContext) -> str:
    if context.overview and context.overview.allergies.strip():
        return context.overview.allergies.strip()
    allergies = context.summary.allergies or []
    return ", ".join(a.strip() for a in allergies if a and str(a).strip()).strip()


def allergies_status_unknown(context: ClinicalContext) -> bool:
    """True when allergy status was never established either way.

    An explicit "no known allergies" is *documented*, so it is not unknown. Only a
    blank field means the question was never answered — which is the P0 safety gap
    the MISSING_DATA object exists to surface.
    """
    return not allergy_text_from_context(context)


def documents_needing_review(context: ClinicalContext) -> tuple[int, ...]:
    """Document ids whose transcription/extraction a human must confirm."""
    return tuple(
        document.document_id
        for document in context.document_evidence
        if document.needs_review
    )


__all__ = [
    "allergies_status_unknown",
    "allergy_text_from_context",
    "documents_needing_review",
    "parse_patient_questions",
    "parse_red_flags",
    "patient_questions_from_context",
    "red_flags_from_context",
]
