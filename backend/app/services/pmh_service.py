from __future__ import annotations

from collections import defaultdict

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pmh import PatientPMH
from app.schemas.pmh import PMHAnswer


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


async def get_patient_pmh(db: AsyncSession, patient_id: int) -> list[PMHAnswer] | None:
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


def format_pmh_for_prompt(answers: list[PMHAnswer]) -> str:
    selected_by_category: dict[str, list[PMHAnswer]] = defaultdict(list)
    for answer in answers:
        if answer.is_selected:
            selected_by_category[answer.category_id].append(answer)

    if not selected_by_category:
        return ""

    lines: list[str] = []
    for category_id in sorted(selected_by_category):
        lines.append(f"[{category_id}]")
        for answer in selected_by_category[category_id]:
            for question_id, response in sorted(answer.question_responses.items()):
                if response is True:
                    lines.append(f"- {question_id}: positive")
                elif isinstance(response, str) and response.strip():
                    lines.append(f"- {question_id}: {response.strip()}")
        lines.append("")

    return "\n".join(lines).strip()
