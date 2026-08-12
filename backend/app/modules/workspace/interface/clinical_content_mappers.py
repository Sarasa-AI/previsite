"""Load allowed adapters and project ClinicalContentResponse.

Composition ownership stays on the backend. Does not reconstruct clinical
facts from Intake when they already exist on ClinicalContext.
"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import File as FileModel
from app.models import Intake, Summary
from app.models import Session as DBSession
from app.modules.workspace.application.projections.adapters import (
    ClinicalContentAdapters,
    DemographicsAdapter,
    DocumentAdapterItem,
    SessionAdapter,
    SoapAdapter,
)
from app.modules.workspace.application.projections.project_clinical_content import (
    project_clinical_content,
)
from app.modules.workspace.interface.clinical_content_dto import ClinicalContentResponse
from app.schemas.clinical_context import ClinicalContext


def _iso(dt) -> str:
    if dt is None:
        return ""
    return dt.isoformat()


async def load_clinical_content_adapters(
    db: AsyncSession,
    session: DBSession,
) -> ClinicalContentAdapters:
    """Load non-ClinicalContext adapter inputs for a session."""
    demographics: DemographicsAdapter | None = None
    intake_result = await db.execute(
        select(Intake).where(Intake.session_id == session.id)
    )
    intake = intake_result.scalar_one_or_none()
    if intake and intake.demographics_json:
        try:
            data = json.loads(intake.demographics_json)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict):
            age_raw = data.get("age")
            age: int | None
            try:
                age = int(age_raw) if age_raw is not None and age_raw != "" else None
            except (TypeError, ValueError):
                age = None
            demographics = DemographicsAdapter(
                first_name=str(data.get("first_name") or "").strip(),
                last_name=str(data.get("last_name") or "").strip(),
                age=age,
                sex=str(data.get("sex") or "").strip(),
                national_id=str(data.get("national_id") or "").strip(),
            )

    files_result = await db.execute(
        select(FileModel)
        .where(FileModel.session_id == session.id)
        .order_by(FileModel.id.asc())
    )
    files = list(files_result.scalars().all())
    documents = tuple(
        DocumentAdapterItem(
            file_id=f.id,
            filename=f.filename or "",
            uploaded_at=_iso(f.created_at),
            detail="",
        )
        for f in files
    )

    soap: SoapAdapter | None = None
    summary_result = await db.execute(
        select(Summary).where(Summary.session_id == session.id)
    )
    summary = summary_result.scalar_one_or_none()
    if summary is not None:
        soap = SoapAdapter(
            soap_note=summary.soap_note,
            legacy_soap_json=summary.legacy_soap_json,
            soap_status=(
                session.soap_status.value
                if session.soap_status is not None
                else ""
            ),
        )

    status = session.status.value if session.status is not None else ""
    generated_at = _iso(session.updated_at) or _iso(session.created_at)

    return ClinicalContentAdapters(
        session=SessionAdapter(
            session_id=session.id,
            status=status,
            visit_type="",
            generated_at=generated_at,
        ),
        demographics=demographics,
        documents=documents,
        soap=soap,
    )


def to_clinical_content_response(
    context: ClinicalContext,
    adapters: ClinicalContentAdapters,
) -> ClinicalContentResponse:
    """Map ClinicalContext + adapters to the versioned wire envelope."""
    return project_clinical_content(context, adapters)
