import json
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.database import get_db
from app.models import Intake, Session as DBSession, Summary, User
from app.schemas.intake import (
    ClinicalSummary,
    DemographicsInput,
    HPIAnswerInput,
    HPIQuestionsResponse,
    IntakeResponse,
    MedicalHistoryInput,
)
from app.services.intake_llm import intake_llm_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/intake", tags=["intake"])


def _get_session_or_403(db: Session, session_id: int, current_user: User) -> DBSession:
    query = db.query(DBSession).filter(DBSession.id == session_id)
    if current_user.role == "patient":
        query = query.filter(DBSession.patient_id == current_user.id)
    session = query.first()
    if not session:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this session")
    return session


def _get_or_create_intake(db: Session, session_id: int) -> Intake:
    intake = db.query(Intake).filter(Intake.session_id == session_id).first()
    if not intake:
        intake = Intake(session_id=session_id, current_layer=1)
        db.add(intake)
        db.commit()
        db.refresh(intake)
    return intake


def _load_json(text: str | None) -> dict | list | None:
    if not text:
        return None
    return json.loads(text)


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


def _save_summary_from_intake(db: Session, session_id: int, intake: Intake) -> None:
    """Persist intake data into the legacy Summary table for clinician access."""
    demographics = _load_json(intake.demographics_json) or {}
    clinical = _load_json(intake.clinical_summary_json) or {}
    history = _load_json(intake.medical_history_json) or {}

    summary = db.query(Summary).filter(Summary.session_id == session_id).first()
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
    db.commit()


@router.get("/{session_id}", response_model=IntakeResponse)
def get_intake(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_session_or_403(db, session_id, current_user)
    intake = db.query(Intake).filter(Intake.session_id == session_id).first()
    if not intake:
        raise HTTPException(status_code=404, detail="Intake not found")
    return _to_response(intake)


@router.post("/{session_id}/layer1", response_model=IntakeResponse)
def save_layer1(
    session_id: int,
    data: DemographicsInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = _get_session_or_403(db, session_id, current_user)
    intake = _get_or_create_intake(db, session_id)

    intake.demographics_json = data.model_dump_json()
    intake.current_layer = 2
    session.initial_complaint = data.chief_complaint
    db.commit()
    db.refresh(intake)
    return _to_response(intake)


@router.post("/{session_id}/layer2/generate", response_model=IntakeResponse)
async def generate_layer2_questions(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_session_or_403(db, session_id, current_user)
    intake = _get_or_create_intake(db, session_id)

    if not intake.demographics_json:
        raise HTTPException(status_code=400, detail="Layer 1 demographics must be completed first")

    demographics = DemographicsInput.model_validate_json(intake.demographics_json)
    questions = await intake_llm_service.generate_hpi_questions(demographics)

    intake.hpi_questions_json = questions.model_dump_json()
    intake.question_strategy = questions.question_strategy
    intake.hpi_answers_json = json.dumps({})
    intake.current_layer = 2
    db.commit()
    db.refresh(intake)
    return _to_response(intake)


@router.post("/{session_id}/layer2/answer", response_model=IntakeResponse)
def save_layer2_answer(
    session_id: int,
    data: HPIAnswerInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_session_or_403(db, session_id, current_user)
    intake = db.query(Intake).filter(Intake.session_id == session_id).first()
    if not intake or not intake.hpi_questions_json:
        raise HTTPException(status_code=400, detail="HPI questions must be generated first")

    answers = _load_json(intake.hpi_answers_json) or {}
    answers[data.question_id] = data.answer
    intake.hpi_answers_json = json.dumps(answers, ensure_ascii=False)

    questions = HPIQuestionsResponse.model_validate_json(intake.hpi_questions_json)
    all_answered = all(q.id in answers for q in questions.questions)

    if all_answered:
        intake.current_layer = 3

    db.commit()
    db.refresh(intake)
    return _to_response(intake)


@router.post("/{session_id}/layer3/generate", response_model=IntakeResponse)
async def generate_layer3_summary(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_session_or_403(db, session_id, current_user)
    intake = db.query(Intake).filter(Intake.session_id == session_id).first()
    if not intake or not intake.demographics_json:
        raise HTTPException(status_code=400, detail="Demographics required")

    demographics = DemographicsInput.model_validate_json(intake.demographics_json)
    hpi_answers = _load_json(intake.hpi_answers_json) or {}

    summary = await intake_llm_service.generate_clinical_summary(demographics, hpi_answers)
    intake.clinical_summary_json = summary.model_dump_json()
    intake.current_layer = 4
    db.commit()
    db.refresh(intake)
    return _to_response(intake)


@router.post("/{session_id}/layer4", response_model=IntakeResponse)
def save_layer4(
    session_id: int,
    data: MedicalHistoryInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_session_or_403(db, session_id, current_user)
    intake = db.query(Intake).filter(Intake.session_id == session_id).first()
    if not intake:
        raise HTTPException(status_code=400, detail="Intake not started")

    intake.medical_history_json = data.model_dump_json()
    intake.current_layer = 5
    db.commit()
    db.refresh(intake)
    return _to_response(intake)


@router.post("/{session_id}/submit", response_model=IntakeResponse)
def submit_intake(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = _get_session_or_403(db, session_id, current_user)
    intake = db.query(Intake).filter(Intake.session_id == session_id).first()
    if not intake:
        raise HTTPException(status_code=400, detail="Intake not found")

    if not intake.medical_history_json or not intake.clinical_summary_json:
        raise HTTPException(status_code=400, detail="All intake layers must be completed before submission")

    _save_summary_from_intake(db, session_id, intake)
    session.status = "pending_review"
    db.commit()
    db.refresh(intake)
    return _to_response(intake)
