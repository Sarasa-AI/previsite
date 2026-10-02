"""On-demand document OCR read API (Fail-Closed)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.session_access import get_authorized_session, is_admin
from app.core.rate_limiter import ocr_read_rate_limit
from app.db.database import get_db
from app.models import File as FileModel
from app.models import Intake
from app.models import User
from app.services.audit_service import (
    AUDIT_ADMIN_CLINICAL_READ,
    AUDIT_OCR_READ,
    record_request_audit,
)
from app.services.medical_overview_service import load_medical_overview_from_intake

router = APIRouter(
    prefix="/api/documents",
    tags=["documents"],
)


class DocumentOcrResponse(BaseModel):
    ocr_text: str


def _not_found() -> HTTPException:
    """Generic 404 — does not reveal whether the file exists."""
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")


def _no_ocr_available() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="no_ocr_available",
    )


@router.get("/{file_id}/ocr", response_model=DocumentOcrResponse)
async def get_document_ocr(
    file_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(ocr_read_rate_limit),
) -> DocumentOcrResponse:
    """Return stored lab OCR for a file, only after session auth.

    Authorized callers: patient owner of the session, the assigned/claiming
    doctor, or an admin under the same doctor-equivalent session policy.
    Resolution is strictly session-scoped: file → file.session_id intake →
    lab_results[] match on condition_id. Never search labs across sessions.
    """
    file_result = await db.execute(select(FileModel).where(FileModel.id == file_id))
    db_file = file_result.scalar_one_or_none()
    if not db_file:
        raise _not_found()

    client_ip = request.client.host if request.client else None
    try:
        await get_authorized_session(
            db,
            db_file.session_id,
            current_user,
            claim=True,
            not_found_as_403=False,
            ip_address=client_ip,
        )
    except HTTPException:
        # Obfuscate authorization failures as 404.
        raise _not_found()

    condition_id = (db_file.condition_id or "").strip()
    if not condition_id:
        raise _no_ocr_available()

    intake_result = await db.execute(
        select(Intake).where(Intake.session_id == db_file.session_id)
    )
    intake = intake_result.scalar_one_or_none()
    overview = load_medical_overview_from_intake(intake)
    if not overview:
        raise _no_ocr_available()

    matched_lab = next(
        (lab for lab in overview.lab_results if lab.id == condition_id),
        None,
    )
    ocr_text = (matched_lab.extracted_data or "").strip() if matched_lab else ""
    if not ocr_text:
        raise _no_ocr_available()

    await record_request_audit(
        db,
        action=AUDIT_OCR_READ,
        user_id=current_user.id,
        resource_type="file",
        resource_id=file_id,
        request=request,
    )
    if is_admin(current_user):
        await record_request_audit(
            db,
            action=AUDIT_ADMIN_CLINICAL_READ,
            user_id=current_user.id,
            resource_type="file",
            resource_id=file_id,
            request=request,
        )

    return DocumentOcrResponse(ocr_text=ocr_text)
