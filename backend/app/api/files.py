from typing import Dict, List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.database import get_db
from app.models import File as FileModel
from app.models import Session as SessionModel
from app.models import User
from app.services.file_processor import file_processor
from app.services.storage_service import storage_service

router = APIRouter(
    prefix="/api/files",
    tags=["files"],
)


@router.post("/{session_id}/upload")
async def upload_file(
    session_id: int,
    file: UploadFile = File(...),
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

    try:
        file_data = await file_processor.save_file(file, session_id)

        db_file = FileModel(
            session_id=session_id,
            filename=file_data["filename"],
            s3_key=file_data["s3_key"],
            size_bytes=file_data["file_size"],
            content_type=file_data["mime_type"],
        )

        db.add(db_file)
        await db.commit()
        await db.refresh(db_file)

        return {
            "id": db_file.id,
            "filename": db_file.filename,
            "file_path": db_file.s3_key,
            "size": db_file.size_bytes,
            "mime_type": db_file.content_type,
        }

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}",
        )


@router.get("/{session_id}/list", response_model=List[Dict])
async def list_files(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """لیست فایل‌های یک جلسه"""
    result = await db.execute(
        select(SessionModel).where(SessionModel.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.patient_id != current_user.id and session.doctor_id != current_user.id:
        if current_user.role != "doctor":
            raise HTTPException(status_code=403, detail="Access denied")

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
        }
        for f in files
    ]


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

    url = await storage_service.get_presigned_url(db_file.s3_key)
    return RedirectResponse(url=url, status_code=307)
