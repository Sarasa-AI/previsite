from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import File as FileModel
from app.schemas.intake import (
    ChronicCondition,
    ChronicConditionWithFiles,
    ClinicalOverviewResponse,
    ConditionFileRef,
    CurrentMedication,
    MedicalOverview,
)

if TYPE_CHECKING:
    from app.models import Intake, Summary


def _join_list_field(value: list[str] | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return "، ".join(item.strip() for item in value if item and str(item).strip())


def normalize_legacy_medical_history(raw: dict | None) -> MedicalOverview:
    if not raw:
        return MedicalOverview()

    if "chronic_conditions" in raw or "allergies" in raw:
        return MedicalOverview.model_validate(raw)

    chronic_conditions: list[ChronicCondition] = []
    for name in raw.get("past_medical_history", []) or []:
        label = str(name).strip()
        if not label or label == "هیچ‌کدام":
            continue
        chronic_conditions.append(
            ChronicCondition(id=str(uuid.uuid4()), name=label, duration="")
        )

    return MedicalOverview(
        allergies=_join_list_field(raw.get("allergy_history")),
        surgical_history=_join_list_field(raw.get("past_surgical_history")),
        family_history=_join_list_field(raw.get("family_history")),
        chronic_conditions=chronic_conditions,
        current_medications=list(raw.get("current_medications") or []),
    )


def load_medical_overview_from_intake(intake: Intake | None) -> MedicalOverview | None:
    if not intake or not intake.medical_history_json:
        return None
    raw = json.loads(intake.medical_history_json)
    return normalize_legacy_medical_history(raw)


def overview_for_storage(overview: MedicalOverview) -> dict:
    payload = overview.model_dump(exclude={"file_condition_map"})
    return payload


def format_conditions_for_summary(conditions: list[ChronicCondition]) -> str | None:
    if not conditions:
        return None
    parts: list[str] = []
    for condition in conditions:
        label = condition.name.strip()
        duration = condition.duration.strip()
        if duration:
            parts.append(f"{label} ({duration})")
        else:
            parts.append(label)
    return "، ".join(parts) if parts else None


def format_medication_for_summary(medication: CurrentMedication, has_file: bool = False) -> str:
    name = medication.name.strip()
    if not name:
        if has_file:
            name = "نامشخص - تصویر پیوست شد"
        else:
            return ""

    dosage_parts = [part for part in (medication.amount.strip(), medication.frequency.strip()) if part]
    if dosage_parts:
        return f"{name} - {' '.join(dosage_parts)}"
    return name


def format_medications_for_summary(
    medications: list[CurrentMedication],
    files_by_condition: dict[str, list[ConditionFileRef]] | None = None,
) -> str | None:
    if not medications:
        return None
    files_by_condition = files_by_condition or {}
    parts: list[str] = []
    for medication in medications:
        has_file = bool(files_by_condition.get(medication.id))
        formatted = format_medication_for_summary(medication, has_file=has_file)
        if formatted:
            parts.append(formatted)
    return "، ".join(parts) if parts else None


def format_medication_display(medication: CurrentMedication, has_file: bool = False) -> str:
    return format_medication_for_summary(medication, has_file=has_file)


def validate_condition_id(overview: MedicalOverview, condition_id: str | None) -> bool:
    return validate_file_link_id(overview, condition_id)


def validate_file_link_id(overview: MedicalOverview, condition_id: str | None) -> bool:
    if not condition_id:
        return True
    if any(c.id == condition_id for c in overview.chronic_conditions):
        return True
    if any(lab.id == condition_id for lab in overview.lab_results):
        return True
    if any(med.id == condition_id for med in overview.current_medications):
        return True
    return True


def is_medication_bind_id(overview: MedicalOverview | None, condition_id: str | None) -> bool:
    if not overview or not condition_id:
        return False
    return any(med.id == condition_id for med in overview.current_medications)


def is_lab_bind_id(overview: MedicalOverview | None, condition_id: str | None) -> bool:
    if not overview or not condition_id:
        return False
    return any(lab.id == condition_id for lab in overview.lab_results)


def update_lab_extracted_data(
    intake: Intake,
    lab_id: str,
    extracted_data: str,
) -> MedicalOverview | None:
    overview = load_medical_overview_from_intake(intake)
    if not overview:
        return None

    updated = False
    lab_results = []
    for lab in overview.lab_results:
        if lab.id == lab_id:
            lab_results.append(lab.model_copy(update={"extracted_data": extracted_data}))
            updated = True
        else:
            lab_results.append(lab)

    if not updated:
        return None

    overview = overview.model_copy(update={"lab_results": lab_results})
    intake.medical_history_json = json.dumps(overview_for_storage(overview))
    return overview


def file_to_ref(file_row: FileModel) -> ConditionFileRef:
    return ConditionFileRef(
        id=file_row.id,
        filename=file_row.filename,
        mime_type=file_row.content_type,
        url=f"/api/files/download/{file_row.id}",
        size_bytes=file_row.size_bytes,
        condition_id=file_row.condition_id,
    )


def build_clinical_overview(
    *,
    hpi: str | None,
    overview: MedicalOverview | None,
    files: list[FileModel],
) -> ClinicalOverviewResponse:
    overview = overview or MedicalOverview()
    files_by_condition: dict[str, list[ConditionFileRef]] = {}
    unlinked: list[ConditionFileRef] = []

    for file_row in files:
        ref = file_to_ref(file_row)
        if file_row.condition_id:
            files_by_condition.setdefault(file_row.condition_id, []).append(ref)
        else:
            unlinked.append(ref)

    conditions_with_files: list[ChronicConditionWithFiles] = []
    for condition in overview.chronic_conditions:
        conditions_with_files.append(
            ChronicConditionWithFiles(
                id=condition.id,
                name=condition.name,
                duration=condition.duration,
                files=files_by_condition.get(condition.id, []),
            )
        )

    return ClinicalOverviewResponse(
        hpi=hpi,
        drug_history=[
            format_medication_display(
                medication,
                has_file=bool(files_by_condition.get(medication.id)),
            )
            for medication in overview.current_medications
            if format_medication_display(
                medication,
                has_file=bool(files_by_condition.get(medication.id)),
            )
        ],
        allergies=overview.allergies,
        surgical_history=overview.surgical_history,
        family_history=overview.family_history,
        chronic_conditions=conditions_with_files,
        unlinked_files=unlinked,
    )


async def link_files_to_conditions(
    db: AsyncSession,
    session_id: int,
    overview: MedicalOverview,
    file_condition_map: dict[int, str] | None = None,
) -> None:
    if not file_condition_map:
        return

    result = await db.execute(
        select(FileModel).where(FileModel.session_id == session_id)
    )
    session_files = {f.id: f for f in result.scalars().all()}

    for file_id, condition_id in file_condition_map.items():
        file_row = session_files.get(file_id)
        if not file_row:
            continue
        if condition_id and not validate_condition_id(overview, condition_id):
            continue
        file_row.condition_id = condition_id or None

    await db.flush()


def parse_legacy_soap(summary: Summary | None) -> dict | None:
    if not summary or not summary.legacy_soap_json:
        return None
    try:
        return json.loads(summary.legacy_soap_json)
    except json.JSONDecodeError:
        return None
