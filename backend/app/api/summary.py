from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging

from app.db.database import get_db

logger = logging.getLogger(__name__)
from app.models import Summary, User, Session as SessionModel
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/summary", tags=["summary"])


@router.get("/{session_id}")
def get_summary(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Optional[dict]:
    """
    دریافت خلاصه SOAP برای یک session
    
    Args:
        session_id: شناسه session
        db: اتصال دیتابیس
        current_user: کاربر احراز هویت شده
    
    Returns:
        خلاصه SOAP یا None
    
    Raises:
        HTTPException: اگر خلاصه یافت نشود
    """
    
    # بررسی مالکیت session (امنیت)
    # بیمار فقط به جلسات خودش دسترسی دارد، اما پزشک و ادمین به همه جلسات دسترسی دارند
    query = db.query(SessionModel).filter(SessionModel.id == session_id)
    
    if current_user.role == "patient":
        query = query.filter(SessionModel.patient_id == current_user.id)
    
    session = query.first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this session"
        )

    # بررسی وجود summary
    summary = db.query(Summary).filter(
        Summary.session_id == session_id
    ).first()
    
    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Summary not found for session {session_id}"
        )
    
    try:
        return {
            "id": summary.id,
            "session_id": summary.session_id,
            "soap_note": summary.soap_note,
            "medical_data": {
                "chief_complaint": summary.chief_complaint,
                "history_present_illness": summary.history_present_illness,
                "past_medical_history": summary.past_medical_history,
                "medications": summary.medications,
                "allergies": summary.allergies,
            },
            "created_at": summary.created_at.isoformat() if summary.created_at else None
        }
    except Exception as e:
        logger.error(f"Error formatting summary: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="خطا در واکشی اطلاعات خلاصه"
        )


@router.get("/session/{session_id}/exists")
def check_summary_exists(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> dict:
    """
    بررسی وجود خلاصه برای session
    
    Returns:
        {"exists": bool}
    """
    
    # بیمار فقط به جلسات خودش دسترسی دارد، اما پزشک و ادمین به همه جلسات دسترسی دارند
    query = db.query(SessionModel).filter(SessionModel.id == session_id)
    
    if current_user.role == "patient":
        query = query.filter(SessionModel.patient_id == current_user.id)
    
    session = query.first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this session"
        )

    summary = db.query(Summary).filter(
        Summary.session_id == session_id
    ).first()
    
    return {"exists": summary is not None}
