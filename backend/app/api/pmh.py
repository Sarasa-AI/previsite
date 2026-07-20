import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.database import get_db
from app.models.pmh import PatientPMH
from app.models.user import User, UserRole
from app.schemas.pmh import PatientOverviewResponse, PatientOverviewSubmission
from app.services.medical_overview_service import strip_ocr_from_overview
from app.services.pmh_service import get_patient_overview, upsert_patient_overview

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pmh", tags=["pmh"])


@router.get("/schema")
async def get_pmh_schema() -> None:
    """Deprecated: nested PMH questionnaire replaced by MedicalOverview."""
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="PMH questionnaire deprecated; use MedicalOverview",
    )


def _require_patient(current_user: User) -> None:
    if current_user.role != UserRole.PATIENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only patients can submit medical overview",
        )


async def _authorize_patient_access(
    db: AsyncSession, patient_id: int, current_user: User
) -> None:
    if current_user.role == UserRole.PATIENT:
        if patient_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot access another patient's overview",
            )
        return

    if current_user.role != UserRole.DOCTOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )


@router.post("/submit", response_model=PatientOverviewResponse)
async def submit_pmh(
    data: PatientOverviewSubmission,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PatientOverviewResponse:
    """Save or update a patient's lean medical overview."""
    _require_patient(current_user)

    if data.patient_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot submit overview for another patient",
        )

    row = await upsert_patient_overview(db, data.patient_id, data.overview)
    await db.commit()
    await db.refresh(row)

    return PatientOverviewResponse(
        patient_id=row.patient_id,
        overview=strip_ocr_from_overview(data.overview),
        last_updated=row.last_updated,
    )


@router.get("/overview/{patient_id}", response_model=PatientOverviewResponse)
async def get_patient_overview_endpoint(
    patient_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PatientOverviewResponse:
    await _authorize_patient_access(db, patient_id, current_user)

    row_overview = await get_patient_overview(db, patient_id)
    result = await db.execute(
        select(PatientPMH).where(PatientPMH.patient_id == patient_id)
    )
    row = result.scalar_one_or_none()

    return PatientOverviewResponse(
        patient_id=patient_id,
        overview=strip_ocr_from_overview(row_overview),
        last_updated=row.last_updated if row else None,
    )
