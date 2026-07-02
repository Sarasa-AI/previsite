from __future__ import annotations

import json
import warnings
from collections import defaultdict
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pmh import PatientPMH
from app.schemas.intake import MedicalOverview
from app.schemas.pmh import PMHAnswer, PMHAssertion

_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "data" / "pmh_schema.json"
_question_lookup: dict[str, str] | None = None
_followup_lookup: dict[str, str] | None = None
_question_meta_lookup: dict[str, dict[str, str]] | None = None


def _load_pmh_lookups() -> tuple[dict[str, str], dict[str, str]]:
    global _question_lookup, _followup_lookup

    if _question_lookup is not None and _followup_lookup is not None:
        return _question_lookup, _followup_lookup

    question_lookup: dict[str, str] = {}
    followup_lookup: dict[str, str] = {}

    with _SCHEMA_PATH.open("r", encoding="utf-8") as f:
        categories = json.load(f)

    for category in categories:
        for question in category.get("questions", []):
            question_id = question.get("id")
            metadata = question.get("physician_metadata") or {}
            concept = metadata.get("concept")
            if question_id and concept:
                question_lookup[question_id] = concept

            for followup in question.get("conditional_followups", []):
                followup_id = followup.get("id")
                followup_label = followup.get("physician_metadata")
                if followup_id and followup_label:
                    followup_lookup[followup_id] = followup_label

    _question_lookup = question_lookup
    _followup_lookup = followup_lookup
    return _question_lookup, _followup_lookup


def _load_pmh_question_meta() -> dict[str, dict[str, str]]:
    """
    Returns a mapping from question_id -> {concept, category_id, subcategory}.

    This is used for deterministic PMH assertion registry construction.
    """
    global _question_meta_lookup
    if _question_meta_lookup is not None:
        return _question_meta_lookup

    with _SCHEMA_PATH.open("r", encoding="utf-8") as f:
        categories = json.load(f)

    meta_lookup: dict[str, dict[str, str]] = {}
    for category in categories:
        category_id = category.get("category_id")
        for question in category.get("questions", []):
            question_id = question.get("id")
            metadata = question.get("physician_metadata") or {}
            concept = metadata.get("concept")
            subcategory = question.get("subcategory")
            if question_id and concept and category_id:
                meta_lookup[question_id] = {
                    "concept": concept,
                    "category_id": category_id,
                    "subcategory": subcategory or "",
                }

    _question_meta_lookup = meta_lookup
    return _question_meta_lookup


def _answers_payload(answers: list[PMHAnswer]) -> dict:
    return {"answers": [answer.model_dump() for answer in answers]}


def _parse_answers_payload(payload: dict | None) -> list[PMHAnswer]:
    if not payload:
        return []
    raw_answers = payload.get("answers", [])
    return [PMHAnswer.model_validate(item) for item in raw_answers]


async def upsert_patient_pmh(
    db: AsyncSession,
    patient_id: int,
    answers: list[PMHAnswer],
) -> PatientPMH:
    """Deprecated: use upsert_patient_overview with MedicalOverview."""
    warnings.warn(
        "upsert_patient_pmh is deprecated; use upsert_patient_overview",
        DeprecationWarning,
        stacklevel=2,
    )
    result = await db.execute(
        select(PatientPMH).where(PatientPMH.patient_id == patient_id)
    )
    row = result.scalar_one_or_none()
    payload = _answers_payload(answers)

    if row:
        row.answers_json = payload
    else:
        row = PatientPMH(patient_id=patient_id, answers_json=payload)
        db.add(row)

    await db.flush()
    await db.refresh(row)
    return row


def _overview_payload(overview: MedicalOverview) -> dict:
    return overview.model_dump(exclude={"file_condition_map"})


async def upsert_patient_overview(
    db: AsyncSession,
    patient_id: int,
    overview: MedicalOverview,
) -> PatientPMH:
    result = await db.execute(
        select(PatientPMH).where(PatientPMH.patient_id == patient_id)
    )
    row = result.scalar_one_or_none()
    payload = _overview_payload(overview)

    if row:
        row.overview_json = payload
    else:
        row = PatientPMH(
            patient_id=patient_id,
            answers_json={"answers": []},
            overview_json=payload,
        )
        db.add(row)

    await db.flush()
    await db.refresh(row)
    return row


async def get_patient_overview(
    db: AsyncSession, patient_id: int
) -> MedicalOverview | None:
    result = await db.execute(
        select(PatientPMH).where(PatientPMH.patient_id == patient_id)
    )
    row = result.scalar_one_or_none()
    if not row or not row.overview_json:
        return None
    try:
        return MedicalOverview.model_validate(row.overview_json)
    except ValidationError:
        return None


async def get_patient_pmh(db: AsyncSession, patient_id: int) -> list[PMHAnswer] | None:
    """Deprecated: use get_patient_overview with MedicalOverview."""
    warnings.warn(
        "get_patient_pmh is deprecated; use get_patient_overview",
        DeprecationWarning,
        stacklevel=2,
    )
    result = await db.execute(
        select(PatientPMH).where(PatientPMH.patient_id == patient_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        return None

    try:
        return _parse_answers_payload(row.answers_json)
    except ValidationError:
        return None


def _format_response_line(
    question_id: str,
    response: str | bool,
    question_lookup: dict[str, str],
    followup_lookup: dict[str, str],
) -> str | None:
    if response is True:
        concept = question_lookup.get(question_id)
        if concept:
            return f"- {concept}"
        return f"- {question_id}: positive"

    if isinstance(response, str) and response.strip():
        value = response.strip()
        followup_label = followup_lookup.get(question_id)
        if followup_label:
            return f"- {followup_label}: {value}"
        return f"- {question_id}: {value}"

    return None


def format_pmh_for_prompt(answers: list[PMHAnswer]) -> str:
    """Deprecated: nested PMH tree replaced by MedicalOverview."""
    warnings.warn(
        "format_pmh_for_prompt is deprecated; use MedicalOverview fields",
        DeprecationWarning,
        stacklevel=2,
    )
    selected_by_category: dict[str, list[PMHAnswer]] = defaultdict(list)
    for answer in answers:
        if answer.is_selected:
            selected_by_category[answer.category_id].append(answer)

    if not selected_by_category:
        return ""

    question_lookup, followup_lookup = _load_pmh_lookups()

    lines: list[str] = []
    for category_id in sorted(selected_by_category):
        lines.append(f"[{category_id}]")
        for answer in selected_by_category[category_id]:
            for question_id, response in sorted(answer.question_responses.items()):
                line = _format_response_line(
                    question_id, response, question_lookup, followup_lookup
                )
                if line:
                    lines.append(line)
        lines.append("")

    return "\n".join(lines).strip()


def build_pmh_assertion_registry(answers: list[PMHAnswer]) -> list[PMHAssertion]:
    """
    Deterministically normalize structured PMH answers into a compact assertion registry.

    Rules (conservative):
    - A checkbox True yields a PRESENT assertion for that concept.
    - A follow-up text value yields a PRESENT assertion for that follow-up's parent concept only if
      the follow-up ID is itself present in the schema lookups (we store as detail on its own row).
    - A category with is_selected=False yields a CATEGORY_DENIED assertion (one per category answer).
    - Absence of a checked question is not treated as denial.
    """
    question_meta = _load_pmh_question_meta()
    question_lookup, followup_lookup = _load_pmh_lookups()

    assertions: list[PMHAssertion] = []
    seen_present: set[str] = set()
    seen_category_denied: set[str] = set()

    for answer in answers:
        # Category-level denial (one assertion per category answer row)
        if not answer.is_selected:
            if answer.category_id and answer.category_id not in seen_category_denied:
                assertions.append(
                    PMHAssertion(
                        assertion_id=answer.category_id,
                        concept=f"Category declined: {answer.category_id}",
                        subcategory=None,
                        category_id=answer.category_id,
                        polarity="category_denied",
                    )
                )
                seen_category_denied.add(answer.category_id)
            continue

        # Selected categories: only explicit checked questions become PRESENT
        for question_id, response in (answer.question_responses or {}).items():
            if response is True:
                meta = question_meta.get(question_id)
                concept = (meta or {}).get("concept") or question_lookup.get(question_id)
                category_id = (meta or {}).get("category_id") or answer.category_id
                subcategory = (meta or {}).get("subcategory") or None
                if concept and category_id and question_id not in seen_present:
                    assertions.append(
                        PMHAssertion(
                            assertion_id=question_id,
                            concept=concept,
                            subcategory=subcategory,
                            category_id=category_id,
                            polarity="present",
                        )
                    )
                    seen_present.add(question_id)
            elif isinstance(response, str) and response.strip():
                # follow-up values (record as detail row; concept is follow-up label if known)
                followup_label = followup_lookup.get(question_id)
                if not followup_label:
                    continue
                # For follow-ups, keep assertion_id as the followup id; category is the answer category.
                if question_id in seen_present:
                    continue
                assertions.append(
                    PMHAssertion(
                        assertion_id=question_id,
                        concept=followup_label,
                        subcategory=None,
                        category_id=answer.category_id,
                        polarity="present",
                        detail=response.strip(),
                    )
                )
                seen_present.add(question_id)

    return assertions
