import json
import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status

logger = logging.getLogger(__name__)
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models import Session as DBSession, Message, User

from app.schemas.chat import (
    SessionCreate,
    SessionResponse,
    MessageCreate,
    MessageResponse,
    ChatHistoryResponse
)

from app.auth.dependencies import get_current_user
from app.core.rate_limiter import chat_rate_limit

from app.services.llm_service import llm_service
from app.services.interview_controller import interview_controller
from app.services.interview_flow import InterviewStage
from app.services.medical_extractor import medical_extractor
from app.services.medical_storage import save_medical_data, save_summary
from app.services.summary_builder import summary_builder
from app.services.soap_generator import soap_generator
from app.schemas.medical import MedicalSummary


router = APIRouter(prefix="/api/chat", tags=["chat"])


def _summary_text_field(value: str | None) -> list[str]:
    if not value or value.strip().lower() in {"نامشخص", "unknown", "n/a", ""}:
        return []
    return [value.strip()]


def _summary_notes(value: str | None) -> str | None:
    if not value or value.strip().lower() in {"نامشخص", "unknown", "n/a", ""}:
        return None
    return value.strip()


def _build_fallback_question(stage: InterviewStage) -> str:
    """Return a deterministic fallback prompt when the LLM is unavailable."""
    fallbacks = {
        InterviewStage.MEDICATIONS: "چه داروهایی در حال حاضر مصرف می‌کنید؟",
        InterviewStage.ALLERGIES: "آیا به دارو یا غذای خاصی حساسیت دارید؟",
        InterviewStage.FAMILY_HISTORY: "در خانواده شما سابقه بیماری مهمی وجود دارد؟",
        InterviewStage.SOCIAL_HISTORY: "آیا سیگار، الکل یا عامل شغلی مرتبطی وجود دارد؟",
        InterviewStage.COMPLETION: "ممنون از همکاری شما. اطلاعات کافی جمع‌آوری شد. ",
        InterviewStage.ASSOCIATED_SYMPTOMS: "آیا علامت دیگری همراه با مشکل فعلی‌تان دارید؟",
        InterviewStage.PAST_MEDICAL_HISTORY: "آیا سابقه بیماری یا جراحی مهمی دارید؟",
        InterviewStage.OPQRST: "لطفاً کمی بیشتر درباره شدت و زمان شروع علائم توضیح دهید.",
    }
    return fallbacks.get(
        stage,
        "لطفا کمی بیشتر درباره مشکل اصلی و زمان شروع آن توضیح دهید.",
    )


# ---------------------------------------------------------
# Create Interview Session
# ---------------------------------------------------------

def _calculate_progress(session: DBSession) -> int:
    """محاسبه درصد پیشرفت بر اساس داده‌های موجود در خلاصه"""
    if session.status == "completed" or session.status == "pending_review":
        return 100
        
    if not session.summary:
        return 10
        
    progress = 20  # پایه برای شروع مصاحبه
    summary = session.summary
    
    if summary.chief_complaint: progress += 20
    if summary.history_present_illness: progress += 20
    if summary.past_medical_history: progress += 10
    if summary.medications: progress += 10
    if summary.allergies: progress += 10
    if summary.soap_note: progress += 10
    
    return min(progress, 95)  # حداکثر ۹۵ قبل از اتمام نهایی


@router.post("/session", response_model=SessionResponse)
def create_session(
    data: SessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """ایجاد جلسه جدید مصاحبه پزشکی"""

    new_session = DBSession(
        patient_id=current_user.id,
        status="active",
        initial_complaint=data.initial_complaint
    )

    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    
    response = SessionResponse.model_validate(new_session)
    response.progress = _calculate_progress(new_session)
    return response


@router.get("/sessions", response_model=list[SessionResponse])
def list_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """لیست جلسات (برای بیمار: جلسات خودش، برای پزشک: تمام جلسات)"""
    query = db.query(DBSession)
    
    if current_user.role == "patient":
        query = query.filter(DBSession.patient_id == current_user.id)
    # پزشک می‌تواند همه جلسات را ببیند (در نسخه MVP)
    
    sessions = query.order_by(DBSession.created_at.desc()).all()
    
    results = []
    for s in sessions:
        resp = SessionResponse.model_validate(s)
        resp.progress = _calculate_progress(s)
        results.append(resp)
        
    return results


async def _process_final_summary(session_id: int, db_gen):
    """پردازش پس‌زمینه برای تولید خلاصه نهایی و SOAP note"""
    db = next(db_gen)
    try:
        logger.info(f"Starting background summary/SOAP processing for session {session_id}")
        db_messages = (
            db.query(Message)
            .filter(Message.session_id == session_id)
            .order_by(Message.created_at)
            .all()
        )
        history = [{"role": m.role, "content": m.content} for m in db_messages]
        
        new_summary_data = await summary_builder.build_summary(history)
        if new_summary_data:
            med_sum = MedicalSummary(
                chief_complaint=new_summary_data.get("chief_complaint"),
                past_medical_history=[new_summary_data.get("past_medical_history")] if new_summary_data.get("past_medical_history") != "نامشخص" else [],
                current_medications=[new_summary_data.get("medications")] if new_summary_data.get("medications") != "نامشخص" else [],
                allergies=[new_summary_data.get("allergies")] if new_summary_data.get("allergies") != "نامشخص" else [],
                additional_notes=new_summary_data.get("history_present_illness"),
            )
            soap_note_result = await soap_generator.generate_soap_note(
                summary=med_sum,
                chat_history=history,
                file_analyses=[]
            )
            soap_note_content = soap_note_result.get("soap_note") if soap_note_result.get("status") == "success" else None
            save_summary(db, session_id, new_summary_data, soap_note=soap_note_content)
            logger.info(f"Background processing completed for session {session_id}")
    except Exception as e:
        logger.error(f"Final background summary/SOAP update error: {e}")
    finally:
        db.close()


@router.post("/{session_id}/submit", response_model=SessionResponse)
async def submit_session(
    session_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """ثبت نهایی و ارسال به پزشک"""
    session = db.query(DBSession).filter(
        DBSession.id == session_id,
        DBSession.patient_id == current_user.id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # به‌روزرسانی نهایی خلاصه و SOAP در پس‌زمینه برای کاهش تأخیر پاسخ‌دهی به کاربر
    background_tasks.add_task(_process_final_summary, session_id, get_db())

    session.status = "pending_review"
    db.commit()
    db.refresh(session)
    
    resp = SessionResponse.model_validate(session)
    resp.progress = _calculate_progress(session)
    return resp


# ---------------------------------------------------------
# Send Message
# ---------------------------------------------------------

@router.post("/{session_id}", response_model=MessageResponse)
async def send_message(
    session_id: int,
    data: MessageCreate,
    _: None = Depends(chat_rate_limit),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """ارسال پیام کاربر و دریافت پاسخ از LLM"""

    # بررسی session
    session = db.query(DBSession).filter(DBSession.id == session_id).first()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # بیمار فقط به تاریخچه چت خودش دسترسی دارد، اما پزشک و ادمین به همه دسترسی دارند
    if current_user.role == "patient" and session.patient_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # -------------------------------------------------
    # ذخیره پیام کاربر
    # -------------------------------------------------

    try:
        user_message = Message(
            session_id=session_id,
            role="user",
            content=data.content
        )

        db.add(user_message)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving user message: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="خطا در ذخیره پیام کاربر"
        )

    # -------------------------------------------------
    # استخراج داده پزشکی و به‌روزرسانی خلاصه
    # -------------------------------------------------
    # نکته: برای کاهش تأخیر، استخراج داده را فقط در صورت نیاز انجام می‌دهیم
    # یا آن را با مرحله تولید پاسخ ترکیب می‌کنیم. فعلاً تعداد پیام‌ها را چک می‌کنیم.
    
    # دریافت آخرین خلاصه از دیتابیس برای اطلاع از وضعیت فعلی
    last_summary = session.summary
    
    current_summary_obj = None
    if last_summary:
        try:
            # نگاشت مدل دیتابیس به اسکیما
            current_summary_obj = MedicalSummary(
                chief_complaint=last_summary.chief_complaint,
                past_medical_history=_summary_text_field(last_summary.past_medical_history),
                current_medications=_summary_text_field(last_summary.medications),
                allergies=_summary_text_field(last_summary.allergies),
                additional_notes=_summary_notes(last_summary.history_present_illness),
            )
        except Exception:
            pass

    # -------------------------------------------------
    # دریافت تاریخچه پیام‌ها (بدون سیستم پرامپت قدیمی)
    # -------------------------------------------------

    db_messages = (
        db.query(Message)
        .filter(Message.session_id == session_id)
        .order_by(Message.created_at)
        .all()
    )
    
    history = []
    for m in db_messages:
        history.append({"role": m.role, "content": m.content})

    # -------------------------------------------------
    # تشخیص مرحله مصاحبه و ساخت پرامپت
    # -------------------------------------------------

    message_count = len(db_messages)
    current_stage = interview_controller.detect_stage(current_summary_obj, history)
    stage_instruction = interview_controller.get_stage_instruction(
        current_stage,
        summary=current_summary_obj,
        chat_history=history,
    )

    # نمایش وضعیت فعلی داده‌ها به LLM برای جلوگیری از تکرار سوالات
    current_data_str = "هنوز داده‌ای استخراج نشده است."
    if current_summary_obj:
        summary_dict = current_summary_obj.model_dump(exclude_none=True, exclude={'extracted_at'})
        current_data_str = json.dumps(summary_dict, ensure_ascii=False, indent=2)

    system_prompt = llm_service.get_system_prompt(
        current_data_str,
        chat_history=history,
        stage_instruction=stage_instruction,
    )

    # -------------------------------------------------
    # دریافت پاسخ از مدل
    # -------------------------------------------------

    try:
        ai_response = await llm_service.chat(history, system_prompt=system_prompt)
    except Exception as e:
        logger.error(f"LLM Chat Error: {str(e)}")
        ai_response = _build_fallback_question(current_stage)

    # -------------------------------------------------
    # ذخیره پاسخ مدل
    # -------------------------------------------------

    try:
        assistant_message = Message(
            session_id=session_id,
            role="assistant",
            content=ai_response
        )

        db.add(assistant_message)
        db.commit()
        db.refresh(assistant_message)
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving assistant message: {str(e)}")
        # Note: We still have the AI response, but we couldn't save it.
        # For better UX, we could return it without saving, but that would break history.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="خطا در ذخیره پاسخ سیستم"
        )

    # -------------------------------------------------
    # به‌روزرسانی خلاصه و استخراج داده (به صورت دوره‌ای یا در صورت تغییر مرحله)
    # -------------------------------------------------
    # برای بهینه‌سازی، فقط هر ۲ پیام یک بار یا در پیام‌های اول خلاصه را آپدیت می‌کنیم
    # message_count + 1 برای در نظر گرفتن پیام اسیستنت که تازه اضافه شده است
    if (message_count + 1) % 2 == 0 or (message_count + 1) < 5:
        try:
            # اضافه کردن پیام جدید به تاریخچه برای خلاصه سازی
            history.append({"role": "assistant", "content": ai_response})
            new_summary_data = await summary_builder.build_summary(history)
            if new_summary_data:
                soap_note_content = None
                # تولید SOAP Note فقط در صورت پیشرفت قابل توجه (مثلاً هر ۴ پیام)
                # message_count + 1 برای در نظر گرفتن پیام اسیستنت که تازه اضافه شده است
                if (message_count + 1) % 4 == 0:
                    try:
                        # تبدیل دیکشنری به مدل MedicalSummary برای SOAP
                        med_sum = MedicalSummary(
                            chief_complaint=new_summary_data.get("chief_complaint"),
                            past_medical_history=[new_summary_data.get("past_medical_history")] if new_summary_data.get("past_medical_history") != "نامشخص" else [],
                            current_medications=[new_summary_data.get("medications")] if new_summary_data.get("medications") != "نامشخص" else [],
                            allergies=[new_summary_data.get("allergies")] if new_summary_data.get("allergies") != "نامشخص" else [],
                            additional_notes=new_summary_data.get("history_present_illness"),
                        )
                        soap_note_result = await soap_generator.generate_soap_note(
                            summary=med_sum,
                            chat_history=history,
                            file_analyses=[]
                        )
                        if soap_note_result and soap_note_result.get("status") == "success":
                            soap_note_content = soap_note_result.get("soap_note")
                    except Exception as soap_err:
                        logger.error(f"SOAP generation error: {soap_err}")
                save_summary(db, session_id, new_summary_data, soap_note=soap_note_content)
        except Exception as sum_err:
            logger.error(f"Summary update error: {sum_err}")

    return assistant_message


# ---------------------------------------------------------
# Chat History
# ---------------------------------------------------------

@router.get("/{session_id}", response_model=ChatHistoryResponse)
def get_chat_history(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """دریافت تاریخچه کامل گفتگو"""

    session = db.query(DBSession).filter(DBSession.id == session_id).first()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # بیمار فقط به تاریخچه چت خودش دسترسی دارد، اما پزشک و ادمین به همه دسترسی دارند
    if current_user.role == "patient" and session.patient_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    messages = (
        db.query(Message)
        .filter(Message.session_id == session_id)
        .order_by(Message.created_at)
        .all()
    )

    return {
        "session": session,
        "messages": messages
    }
