import logging
from typing import Dict, List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.database import get_db
from app.models import File as FileModel
from app.models import Session as SessionModel
from app.models import User
from app.schemas.intake import FileConditionLink
from app.services.file_processor import file_processor
from app.services.medical_overview_service import (
    is_lab_bind_id,
    load_medical_overview_from_intake,
    update_lab_extracted_data,
    validate_file_link_id,
)
from app.services.ocr_service import extract_lab_values_ocr, extract_medication_ocr
from app.services.storage_service import storage_service
from app.models import Intake

router = APIRouter(
    prefix="/api/files",
    tags=["files"],
)

logger = logging.getLogger(__name__)


async def _get_authorized_session(
    db: AsyncSession, session_id: int, current_user: User
) -> SessionModel:
    result = await db.execute(
        select(SessionModel).where(SessionModel.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.patient_id != current_user.id and session.doctor_id != current_user.id:
        if current_user.role != "doctor":
            raise HTTPException(status_code=403, detail="Access denied")
    return session


@router.post("/{session_id}/upload")
async def upload_file(
    session_id: int,
    file: UploadFile = File(...),
    condition_id: str | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict:
    """آپلود فایل برای یک session"""
    result = await db.execute(
        select(SessionModel).where(
            SessionModel.id == session_id,
            SessionModel.patient_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or access denied",
        )

    extracted_data: str | None = None
    extracted_medication_name: str | None = None
    intake_for_ocr: Intake | None = None

    if condition_id:
        intake_result = await db.execute(
            select(Intake).where(Intake.session_id == session_id)
        )
        intake_for_ocr = intake_result.scalar_one_or_none()
        overview = load_medical_overview_from_intake(intake_for_ocr)
        if overview and not validate_file_link_id(overview, condition_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="condition_id does not match any chronic condition, medication, or lab result in this session",
            )

    medication_ocr_attempted = False

    try:
        file_data = await file_processor.save_file(file, session_id)

        db_file = FileModel(
            session_id=session_id,
            filename=file_data["filename"],
            s3_key=file_data["s3_key"],
            size_bytes=file_data["file_size"],
            content_type=file_data["mime_type"],
            condition_id=condition_id,
        )

        db.add(db_file)
        await db.commit()
        await db.refresh(db_file)
    except HTTPException:
        await db.rollback()
        raise
    except Exception:
        await db.rollback()
        logger.exception("File upload failed for session_id=%s", session_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Upload failed",
        )

    if condition_id:
        overview = load_medical_overview_from_intake(intake_for_ocr)
        mime_type = db_file.content_type or ""
        is_chronic = bool(
            overview and any(c.id == condition_id for c in overview.chronic_conditions)
        )
        if mime_type.startswith("image/"):
            try:
                image_bytes = file_data["content"]
                if is_lab_bind_id(overview, condition_id):
                    extracted_data = extract_lab_values_ocr(image_bytes)
                    if extracted_data and intake_for_ocr and update_lab_extracted_data(
                        intake_for_ocr, condition_id, extracted_data
                    ):
                        await db.commit()
                elif not is_chronic:
                    medication_ocr_attempted = True
                    extracted_medication_name = extract_medication_ocr(image_bytes, mime_type)
            except Exception as e:
                logger.error(
                    "OCR extraction failed for session_id=%s condition_id=%s: %s",
                    session_id,
                    condition_id,
                    e,
                )
                extracted_data = None
                extracted_medication_name = None

    response: Dict = {
        "id": db_file.id,
        "filename": db_file.filename,
        "file_path": db_file.s3_key,
        "size": db_file.size_bytes,
        "mime_type": db_file.content_type,
        "condition_id": db_file.condition_id,
    }
    if extracted_data is not None:
        response["extracted_data"] = extracted_data
    if extracted_medication_name is not None:
        response["extracted_medication_name"] = extracted_medication_name
    elif medication_ocr_attempted:
        response["extracted_medication_name"] = None
    return response


@router.get("/{session_id}/list", response_model=List[Dict])
async def list_files(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """لیست فایل‌های یک جلسه"""
    await _get_authorized_session(db, session_id, current_user)

    files_result = await db.execute(
        select(FileModel).where(FileModel.session_id == session_id)
    )
    files = files_result.scalars().all()
    return [
        {
            "id": f.id,
            "filename": f.filename,
            "size": f.size_bytes,
            "mime_type": f.content_type,
            "url": f"/api/files/download/{f.id}",
            "condition_id": f.condition_id,
        }
        for f in files
    ]


@router.patch("/{session_id}/files/{file_id}")
async def link_file_to_condition(
    session_id: int,
    file_id: int,
    data: FileConditionLink,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict:
    await _get_authorized_session(db, session_id, current_user)

    file_result = await db.execute(
        select(FileModel).where(
            FileModel.id == file_id,
            FileModel.session_id == session_id,
        )
    )
    db_file = file_result.scalar_one_or_none()
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")

    if data.condition_id:
        intake_result = await db.execute(
            select(Intake).where(Intake.session_id == session_id)
        )
        intake = intake_result.scalar_one_or_none()
        overview = load_medical_overview_from_intake(intake)
        if overview and not validate_file_link_id(overview, data.condition_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="condition_id does not match any chronic condition, medication, or lab result in this session",
            )

    db_file.condition_id = data.condition_id
    await db.commit()
    await db.refresh(db_file)

    return {
        "id": db_file.id,
        "filename": db_file.filename,
        "condition_id": db_file.condition_id,
    }


@router.get("/download/{file_id}")
async def download_file(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """دانلود/مشاهده فایل"""
    file_result = await db.execute(
        select(FileModel).where(FileModel.id == file_id)
    )
    db_file = file_result.scalar_one_or_none()
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")

    session_result = await db.execute(
        select(SessionModel).where(SessionModel.id == db_file.session_id)
    )
    session = session_result.scalar_one_or_none()

    if session.patient_id != current_user.id and session.doctor_id != current_user.id:
        if current_user.role != "doctor":
            raise HTTPException(status_code=403, detail="Access denied")

    if getattr(storage_service, "is_local", False):
        try:
            content = await storage_service.download_file(db_file.s3_key)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="File not found in storage")
        return Response(
            content=content,
            media_type=db_file.content_type or "application/octet-stream",
            headers={"Content-Disposition": f'inline; filename="{db_file.filename}"'},
        )

    url = await storage_service.get_presigned_url(db_file.s3_key)
    return RedirectResponse(url=url, status_code=307)
