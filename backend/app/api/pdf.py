import io
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.session_access import get_authorized_session, is_doctor
from app.core.config import settings
from app.db.database import get_db
from app.models import Intake, Summary, User
from app.models import Session as DBSession
from app.schemas.intake import ClinicalSummary, DemographicsInput
from app.services.audit_service import record_audit
from app.services.medical_overview_service import load_medical_overview_from_intake
from app.services.pdf_service import generate_patient_report_pdf

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


class SoapUpdateRequest(BaseModel):
    soap_note: str = Field(..., min_length=1)


class SoapUpdateResponse(BaseModel):
    session_id: int
    soap_note: str


async def _get_session_or_403(
    db: AsyncSession, session_id: int, current_user: User
) -> DBSession:
    return await get_authorized_session(db, session_id, current_user, claim=True)


@router.patch("/{session_id}/soap", response_model=SoapUpdateResponse)
async def update_session_soap(
    session_id: int,
    body: SoapUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SoapUpdateResponse:
    """Overwrite SOAP note text for an assigned/claimable session (doctor only).

    Not full track-changes — previous text is stored on the audit row only.
    """
    if not is_doctor(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only doctors can edit SOAP notes",
        )

    await _get_session_or_403(db, session_id, current_user)

    sum_result = await db.execute(
        select(Summary).where(Summary.session_id == session_id)
    )
    summary = sum_result.scalar_one_or_none()
    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Summary not found for session {session_id}",
        )

    previous = summary.soap_note
    summary.soap_note = body.soap_note
    await db.commit()
    await db.refresh(summary)

    client_ip = request.client.host if request.client else None
    await record_audit(
        db,
        action="edit_soap",
        user_id=current_user.id,
        resource_type="session",
        resource_id=session_id,
        ip_address=client_ip,
        previous_value=previous,
    )

    return SoapUpdateResponse(session_id=session_id, soap_note=summary.soap_note or "")


@router.get("/{session_id}/pdf")
async def download_patient_report_pdf(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Generate and download a clinical patient report PDF for a session."""
    await _get_session_or_403(db, session_id, current_user)

    intake_result = await db.execute(select(Intake).where(Intake.session_id == session_id))
    intake = intake_result.scalar_one_or_none()
    if not intake:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Intake not found for session {session_id}",
        )

    medical_overview = load_medical_overview_from_intake(intake)
    if medical_overview is None:
        from app.schemas.intake import MedicalOverview

        medical_overview = MedicalOverview()

    clinical_summary = None
    if intake.clinical_summary_json:
        clinical_summary = ClinicalSummary.model_validate_json(intake.clinical_summary_json)

    demographics = None
    if intake.demographics_json:
        demographics = DemographicsInput.model_validate_json(intake.demographics_json)

    patient_name = "—"
    if demographics:
        patient_name = f"{demographics.first_name} {demographics.last_name}".strip() or "—"

    session_data = {
        "session_id": session_id,
        "clinic_name": settings.openrouter_app_title,
        "report_date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "patient_name": patient_name,
        "clinical_summary": clinical_summary,
        "demographics": demographics,
    }

    try:
        pdf_bytes = generate_patient_report_pdf(session_data, medical_overview)
    except Exception:
        logger.exception("PDF generation failed for session_id=%s", session_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate patient report PDF",
        ) from None

    filename = f"patient_report_{session_id}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
