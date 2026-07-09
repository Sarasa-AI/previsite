import io
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.config import settings
from app.db.database import get_db
from app.models import Intake, User
from app.models import Session as DBSession
from app.schemas.intake import ClinicalSummary, DemographicsInput
from app.services.medical_overview_service import load_medical_overview_from_intake
from app.services.pdf_service import generate_patient_report_pdf

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions", tags=["pdf"])


async def _get_session_or_403(
    db: AsyncSession, session_id: int, current_user: User
) -> DBSession:
    query = select(DBSession).where(DBSession.id == session_id)
    if current_user.role == "patient":
        query = query.where(DBSession.patient_id == current_user.id)
    result = await db.execute(query)
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this session",
        )
    return session


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
