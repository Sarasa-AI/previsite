import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.database import get_db
from app.models import Intake, Summary, User
from app.models import Session as DBSession
from app.schemas.intake import (
    ClinicalSummary,
    DemographicsInput,
    HPIAnswerInput,
    HPIQuestionsResponse,
    IntakeResponse,
    MedicalHistoryInput,
)
from app.services.intake_llm import intake_llm_service
from app.services.soap_task import trigger_soap_generation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/intake", tags=["intake"])


async def _get_session_or_403(
    db: AsyncSession, session_id: int, current_user: User
) -> DBSession:
    query = select(DBSession).where(DBSession.id == session_id)
    if current_user.role == "patient":
        query = query.where(DBSession.patient_id == current_user.id)
    result = await db.execute(query)
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this session")
    return session


async def _get_or_create_intake(db: AsyncSession, session_id: int) -> Intake:
    result = await db.execute(select(Intake).where(Intake.session_id == session_id))
    intake = result.scalar_one_or_none()
    if not intake:
        intake = Intake(session_id=session_id, current_layer=1)
        db.add(intake)
        await db.commit()
        await db.refresh(intake)
    return intake


def _load_json(text: str | None) -> dict | list | None:
    if not text:
        return None
    return json.loads(text)


def _sync_patient_profile(user: User, data: DemographicsInput) -> None:
    """Persist per-patient demographic fields on the user profile."""
    user.first_name = data.first_name
    user.last_name = data.last_name
    if data.national_id:
        user.national_id = data.national_id
    user.age = data.age
    user.sex = data.sex
    user.weight = data.weight
    user.height = data.height
    user.full_name = f"{data.first_name} {data.last_name}".strip()


def _to_response(intake: Intake) -> IntakeResponse:
    demographics = _load_json(intake.demographics_json)
    hpi_questions = _load_json(intake.hpi_questions_json)
    hpi_answers = _load_json(intake.hpi_answers_json)
    clinical_summary = _load_json(intake.clinical_summary_json)
    medical_history = _load_json(intake.medical_history_json)

    return IntakeResponse(
        id=intake.id,
        session_id=intake.session_id,
        current_layer=intake.current_layer,
        demographics=DemographicsInput.model_validate(demographics) if demographics else None,
        hpi_questions=HPIQuestionsResponse.model_validate(hpi_questions) if hpi_questions else None,
        hpi_answers=hpi_answers if isinstance(hpi_answers, dict) else None,
        clinical_summary=ClinicalSummary.model_validate(clinical_summary) if clinical_summary else None,
        medical_history=MedicalHistoryInput.model_validate(medical_history) if medical_history else None,
        created_at=intake.created_at,
        updated_at=intake.updated_at,
    )


async def _save_summary_from_intake(
    db: AsyncSession, session_id: int, intake: Intake
) -> None:
    """Persist intake data into the legacy Summary table for clinician access."""
    demographics = _load_json(intake.demographics_json) or {}
    clinical = _load_json(intake.clinical_summary_json) or {}
    history = _load_json(intake.medical_history_json) or {}

    result = await db.execute(select(Summary).where(Summary.session_id == session_id))
    summary = result.scalar_one_or_none()
    if not summary:
        summary = Summary(session_id=session_id)
        db.add(summary)

    summary.chief_complaint = clinical.get("chief_complaint") or demographics.get("chief_complaint")
    summary.history_present_illness = clinical.get("hpi_summary")
    summary.past_medical_history = "، ".join(history.get("past_medical_history", [])) or None
    summary.allergies = "، ".join(history.get("allergy_history", [])) or None
    summary.assessment = json.dumps(
        {
            "pertinent_positives": clinical.get("pertinent_positives", []),
            "pertinent_negatives": clinical.get("pertinent_negatives", []),
            "red_flags": clinical.get("red_flags", []),
            "past_surgical_history": history.get("past_surgical_history", []),
            "family_history": history.get("family_history", []),
            "demographics": demographics,
        },
        ensure_ascii=False,
    )
    await db.commit()


@router.get("/{session_id}", response_model=IntakeResponse)
async def get_intake(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_session_or_403(db, session_id, current_user)
    intake = await _get_or_create_intake(db, session_id)
    return _to_response(intake)


@router.post("/{session_id}/layer1", response_model=IntakeResponse)
async def save_layer1(
    session_id: int,
    data: DemographicsInput,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = await _get_session_or_403(db, session_id, current_user)
    intake = await _get_or_create_intake(db, session_id)

    if current_user.role == "patient":
        _sync_patient_profile(current_user, data)

    intake.demographics_json = data.model_dump_json()
    intake.current_layer = 2
    session.initial_complaint = data.chief_complaint
    await db.commit()
    await db.refresh(intake)
    return _to_response(intake)


@router.post("/{session_id}/layer2/generate", response_model=IntakeResponse)
async def generate_layer2_questions(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_session_or_403(db, session_id, current_user)
    intake = await _get_or_create_intake(db, session_id)

    if not intake.demographics_json:
        raise HTTPException(status_code=400, detail="Layer 1 demographics must be completed first")

    demographics = DemographicsInput.model_validate_json(intake.demographics_json)
    questions = await intake_llm_service.generate_hpi_questions(demographics)

    intake.hpi_questions_json = questions.model_dump_json()
    intake.question_strategy = questions.question_strategy
    intake.hpi_answers_json = json.dumps({})
    intake.current_layer = 2
    await db.commit()
    await db.refresh(intake)
    return _to_response(intake)


@router.post("/{session_id}/layer2/answer", response_model=IntakeResponse)
async def save_layer2_answer(
    session_id: int,
    data: HPIAnswerInput,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_session_or_403(db, session_id, current_user)
    result = await db.execute(select(Intake).where(Intake.session_id == session_id))
    intake = result.scalar_one_or_none()
    if not intake or not intake.hpi_questions_json:
        raise HTTPException(status_code=400, detail="HPI questions must be generated first")

    answers = _load_json(intake.hpi_answers_json) or {}
    answers[data.question_id] = data.answer
    intake.hpi_answers_json = json.dumps(answers, ensure_ascii=False)

    questions = HPIQuestionsResponse.model_validate_json(intake.hpi_questions_json)
    all_answered = all(q.id in answers for q in questions.questions)

    if all_answered:
        intake.current_layer = 3

    await db.commit()
    await db.refresh(intake)
    return _to_response(intake)


@router.post("/{session_id}/layer3/generate", response_model=IntakeResponse)
async def generate_layer3_summary(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_session_or_403(db, session_id, current_user)
    result = await db.execute(select(Intake).where(Intake.session_id == session_id))
    intake = result.scalar_one_or_none()
    if not intake or not intake.demographics_json:
        raise HTTPException(status_code=400, detail="Demographics required")

    demographics = DemographicsInput.model_validate_json(intake.demographics_json)
    hpi_answers = _load_json(intake.hpi_answers_json) or {}

    summary = await intake_llm_service.generate_clinical_summary(demographics, hpi_answers)
    intake.clinical_summary_json = summary.model_dump_json()
    intake.current_layer = 4
    await db.commit()
    await db.refresh(intake)
    return _to_response(intake)


@router.post("/{session_id}/layer4", response_model=IntakeResponse)
async def save_layer4(
    session_id: int,
    data: MedicalHistoryInput,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_session_or_403(db, session_id, current_user)
    result = await db.execute(select(Intake).where(Intake.session_id == session_id))
    intake = result.scalar_one_or_none()
    if not intake:
        raise HTTPException(status_code=400, detail="Intake not started")

    intake.medical_history_json = data.model_dump_json()
    intake.current_layer = 5
    await db.commit()
    await db.refresh(intake)
    return _to_response(intake)


@router.post("/{session_id}/submit", response_model=IntakeResponse)
async def submit_intake(
    session_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = await _get_session_or_403(db, session_id, current_user)
    result = await db.execute(select(Intake).where(Intake.session_id == session_id))
    intake = result.scalar_one_or_none()
    if not intake:
        raise HTTPException(status_code=400, detail="Intake not found")

    if not intake.medical_history_json or not intake.clinical_summary_json:
        raise HTTPException(status_code=400, detail="All intake layers must be completed before submission")

    await _save_summary_from_intake(db, session_id, intake)
    session.status = "pending_review"
    session.soap_status = "generating"
    session.soap_error_detail = None
    await db.commit()

    trigger_soap_generation(background_tasks, session_id)

    await db.refresh(intake)
    return _to_response(intake)
