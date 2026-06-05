from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import Dict, List
import os

from app.db.database import get_db
from app.services.file_service import file_service
from app.models import File as FileModel, Session as SessionModel, User
from app.auth.dependencies import get_current_user

router = APIRouter(
    prefix="/api/files",
    tags=["files"]
)


@router.post("/{session_id}/upload")
async def upload_file(
    session_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict:
    """
    آپلود فایل برای یک session
    """

    # ✅ بررسی مالکیت session
    session = db.query(SessionModel).filter(
        SessionModel.id == session_id,
        SessionModel.patient_id == current_user.id
    ).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or access denied"
        )

    try:
        # ✅ ذخیره فایل روی دیسک
        file_data = await file_service.save_file(file, session_id)

        # ✅ ثبت در دیتابیس
        db_file = FileModel(
            session_id=session_id,
            filename=file_data["filename"],
            file_path=file_data["file_path"],
            file_size=file_data["file_size"],
            mime_type=file_data["mime_type"]
        )

        db.add(db_file)
        db.commit()
        db.refresh(db_file)

        return {
            "id": db_file.id,
            "filename": db_file.filename,
            "file_path": db_file.file_path,
            "size": db_file.file_size,
            "mime_type": db_file.mime_type
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}"
        )


@router.get("/{session_id}/list", response_model=List[Dict])
def list_files(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """لیست فایل‌های یک جلسه"""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # اجازه دسترسی به بیمار یا پزشک (اگر پزشک اختصاص داده شده باشد)
    if session.patient_id != current_user.id and session.doctor_id != current_user.id:
         # اگر یوزر پزشک است ولی هنوز اختصاص داده نشده، در MVP اجازه می‌دهیم لیست را ببیند
         if current_user.role != "doctor":
            raise HTTPException(status_code=403, detail="Access denied")

    files = db.query(FileModel).filter(FileModel.session_id == session_id).all()
    return [
        {
            "id": f.id,
            "filename": f.filename,
            "size": f.file_size,
            "mime_type": f.mime_type,
            "url": f"/api/files/download/{f.id}"
        }
        for f in files
    ]


@router.get("/download/{file_id}")
def download_file(
    file_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """دانلود/مشاهده فایل"""
    db_file = db.query(FileModel).filter(FileModel.id == file_id).first()
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    session = db.query(SessionModel).filter(SessionModel.id == db_file.session_id).first()
    
    # اجازه دسترسی به بیمار یا پزشک
    if session.patient_id != current_user.id and session.doctor_id != current_user.id:
        if current_user.role != "doctor":
            raise HTTPException(status_code=403, detail="Access denied")

    if not os.path.exists(db_file.file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        path=db_file.file_path,
        filename=db_file.filename,
        media_type=db_file.mime_type
    )
