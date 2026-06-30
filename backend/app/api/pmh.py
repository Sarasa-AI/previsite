import json
import logging
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.database import get_db
from app.models.user import User, UserRole
from app.schemas.pmh import PMHSchemaResponse, PMHSubmission, PMHSubmissionResponse
from app.services.pmh_service import upsert_patient_pmh

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pmh", tags=["pmh"])

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = BACKEND_ROOT / "data" / "pmh_schema.json"


@router.get("/schema", response_model=PMHSchemaResponse)
async def get_pmh_schema(response: Response) -> PMHSchemaResponse:
    """Return the static PMH questionnaire schema (no PII/PHI)."""
    if not DATA_PATH.is_file():
        logger.error("PMH schema file not found: %s", DATA_PATH)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PMH schema data unavailable",
        )

    try:
        async with aiofiles.open(DATA_PATH, "r", encoding="utf-8") as f:
            raw = json.loads(await f.read())
        schema = PMHSchemaResponse.model_validate(raw)
    except (json.JSONDecodeError, ValidationError):
        logger.exception("PMH schema validation failed for %s", DATA_PATH)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PMH schema data is invalid",
        ) from None

    response.headers["Cache-Control"] = "public, max-age=3600"
    return schema


def _require_patient(current_user: User) -> None:
    if current_user.role != UserRole.PATIENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only patients can submit PMH",
        )


@router.post("/submit", response_model=PMHSubmissionResponse)
async def submit_pmh(
    data: PMHSubmission,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PMHSubmissionResponse:
    """Save or update a patient's structured past medical history."""
    _require_patient(current_user)

    if data.patient_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot submit PMH for another patient",
        )

    row = await upsert_patient_pmh(db, data.patient_id, data.answers)
    await db.commit()
    await db.refresh(row)

    return PMHSubmissionResponse(
        patient_id=row.patient_id,
        last_updated=row.last_updated,
        answer_count=len(data.answers),
    )
