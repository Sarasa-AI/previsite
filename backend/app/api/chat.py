import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import get_current_user
from app.core.rate_limiter import chat_rate_limit
from app.db.database import get_async_session, get_db
from app.models import Message, User
from app.models import Session as DBSession
from app.schemas.chat import (
    ChatHistoryResponse,
    MessageCreate,
    MessageResponse,
    SessionCreate,
    SessionResponse,
)
from app.schemas.medical import MedicalSummary
from app.services.interview_controller import interview_controller
from app.services.interview_flow import InterviewStage
from app.services.llm_service import llm_service
from app.services.medical_storage import save_summary
from app.services.soap_task import run_soap_generation
from app.services.summary_builder import summary_builder

logger = logging.getLogger(__name__)

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


def _patient_display_name(user: User | None) -> str | None:
    if not user:
        return None
    if user.full_name and user.full_name.strip():
        return user.full_name.strip()
    parts = f"{user.first_name or ''} {user.last_name or ''}".strip()
    return parts or None


def _calculate_progress(session: DBSession) -> int:
    """محاسبه درصد پیشرفت بر اساس داده‌های موجود در خلاصه"""
    if session.status == "completed" or session.status == "pending_review":
        return 100

    if "summary" in sa_inspect(session).unloaded:
        return 10

    if not session.summary:
        return 10

    progress = 20
    summary = session.summary

    if summary.chief_complaint:
        progress += 20
    if summary.history_present_illness:
        progress += 20
    if summary.past_medical_history:
        progress += 10
    if summary.medications:
        progress += 10
    if summary.allergies:
        progress += 10
    if summary.soap_note:
        progress += 10

    return min(progress, 95)


@router.post("/session", response_model=SessionResponse)
async def create_session(
    data: SessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """ایجاد جلسه جدید مصاحبه پزشکی"""
    new_session = DBSession(
        patient_id=current_user.id,
        status="active",
        initial_complaint=data.initial_complaint,
    )

    db.add(new_session)
    await db.commit()
    await db.refresh(new_session)

    response = SessionResponse.model_validate(new_session)
    response.progress = _calculate_progress(new_session)
    return response


@router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """لیست جلسات (برای بیمار: جلسات خودش، برای پزشک: تمام جلسات)"""
    query = select(DBSession).options(
        selectinload(DBSession.summary),
        selectinload(DBSession.patient),
    )

    if current_user.role == "patient":
        query = query.where(DBSession.patient_id == current_user.id)

    query = query.order_by(DBSession.created_at.desc())
    result = await db.execute(query)
    sessions = result.scalars().all()

    results = []
    for s in sessions:
        resp = SessionResponse.model_validate(s)
        resp.patient_name = _patient_display_name(s.patient)
        resp.progress = _calculate_progress(s)
        results.append(resp)

    return results


async def _process_final_summary(session_id: int) -> None:
    """پردازش پس‌زمینه برای تولید خلاصه نهایی و SOAP note"""
    async with get_async_session() as db:
        try:
            logger.info("Starting background summary/SOAP processing for session %s", session_id)
            result = await db.execute(
                select(DBSession).where(DBSession.id == session_id)
            )
            session = result.scalar_one_or_none()
            if session:
                session.soap_status = "generating"
                session.soap_error_detail = None
                await db.commit()

            msg_result = await db.execute(
                select(Message)
                .where(Message.session_id == session_id)
                .order_by(Message.created_at)
            )
            db_messages = msg_result.scalars().all()
            history = [{"role": m.role, "content": m.content} for m in db_messages]

            new_summary_data = await summary_builder.build_summary(history)
            if new_summary_data:
                await save_summary(db, session_id, new_summary_data)
                logger.info("Summary saved for session %s, starting SOAP generation", session_id)
        except Exception as e:
            logger.error("Final background summary update error: %s", e)

    await run_soap_generation(session_id)


@router.post("/{session_id}/submit", response_model=SessionResponse)
async def submit_session(
    session_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """ثبت نهایی و ارسال به پزشک"""
    result = await db.execute(
        select(DBSession)
        .options(selectinload(DBSession.summary))
        .where(
            DBSession.id == session_id,
            DBSession.patient_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    background_tasks.add_task(_process_final_summary, session_id)

    session.status = "pending_review"
    session.soap_status = "generating"
    session.soap_error_detail = None
    await db.commit()
    await db.refresh(session)

    resp = SessionResponse.model_validate(session)
    resp.progress = _calculate_progress(session)
    return resp


@router.post("/{session_id}", response_model=MessageResponse)
async def send_message(
    session_id: int,
    data: MessageCreate,
    _: None = Depends(chat_rate_limit),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """ارسال پیام کاربر و دریافت پاسخ از LLM"""
    result = await db.execute(
        select(DBSession)
        .options(selectinload(DBSession.summary))
        .where(DBSession.id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if current_user.role == "patient" and session.patient_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        user_message = Message(
            session_id=session_id,
            role="user",
            content=data.content,
        )
        db.add(user_message)
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error("Error saving user message: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="خطا در ذخیره پیام کاربر",
        )

    last_summary = session.summary

    current_summary_obj = None
    if last_summary:
        try:
            current_summary_obj = MedicalSummary(
                chief_complaint=last_summary.chief_complaint,
                past_medical_history=_summary_text_field(last_summary.past_medical_history),
                current_medications=_summary_text_field(last_summary.medications),
                allergies=_summary_text_field(last_summary.allergies),
                additional_notes=_summary_notes(last_summary.history_present_illness),
                is_hpi_complete=getattr(last_summary, "is_hpi_complete", False) or False,
            )
        except Exception:
            pass

    msg_result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at)
    )
    db_messages = msg_result.scalars().all()

    history = []
    for m in db_messages:
        history.append({"role": m.role, "content": m.content})

    message_count = len(db_messages)
    current_stage = interview_controller.detect_stage(current_summary_obj, history)
    stage_instruction = interview_controller.get_stage_instruction(
        current_stage,
        summary=current_summary_obj,
        chat_history=history,
    )

    current_data_str = "هنوز داده‌ای استخراج نشده است."
    if current_summary_obj:
        summary_dict = current_summary_obj.model_dump(exclude_none=True, exclude={"extracted_at"})
        current_data_str = json.dumps(summary_dict, ensure_ascii=False, indent=2)

    system_prompt = llm_service.get_system_prompt(
        current_data_str,
        chat_history=history,
        stage_instruction=stage_instruction,
    )

    try:
        ai_response = await llm_service.chat(
            history,
            system_prompt=system_prompt,
            tier3_factory=lambda: _build_fallback_question(current_stage),
        )
    except Exception as e:
        logger.error("LLM Chat Error: %s", str(e))
        ai_response = _build_fallback_question(current_stage)

    try:
        assistant_message = Message(
            session_id=session_id,
            role="assistant",
            content=ai_response,
        )
        db.add(assistant_message)
        await db.commit()
        await db.refresh(assistant_message)
    except Exception as e:
        await db.rollback()
        logger.error("Error saving assistant message: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="خطا در ذخیره پاسخ سیستم",
        )

    if (message_count + 1) % 2 == 0 or (message_count + 1) < 5:
        try:
            history.append({"role": "assistant", "content": ai_response})
            new_summary_data = await summary_builder.build_summary(history)
            if new_summary_data:
                await save_summary(db, session_id, new_summary_data)
        except Exception as sum_err:
            logger.error("Summary update error: %s", sum_err)

    return assistant_message


@router.get("/{session_id}", response_model=ChatHistoryResponse)
async def get_chat_history(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """دریافت تاریخچه کامل گفتگو"""
    result = await db.execute(
        select(DBSession).where(DBSession.id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if current_user.role == "patient" and session.patient_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    msg_result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at)
    )
    messages = msg_result.scalars().all()

    return {
        "session": session,
        "messages": messages,
    }
