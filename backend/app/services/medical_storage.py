from typing import Optional
from sqlalchemy.orm import Session
from app.models import Summary  


def save_medical_data(db: Session, session_id: int, data: dict):

    if not data:
        return

    summary = db.query(Summary).filter(
        Summary.session_id == session_id
    ).first()

    if not summary:

        summary = Summary(
            session_id=session_id,
            chief_complaint=data.get("chief_complaint"),
            history_present_illness=str(data.get("symptoms")),
            past_medical_history=str(data.get("past_diseases")),
            medications=str(data.get("medications")),
            allergies=str(data.get("allergies")),
            assessment=""
        )

        db.add(summary)

    else:

        if data.get("chief_complaint"):
            summary.chief_complaint = data["chief_complaint"]

        if data.get("medications"):
            summary.medications = str(data["medications"])

        if data.get("allergies"):
            summary.allergies = str(data["allergies"])

        if data.get("past_diseases"):
            summary.past_medical_history = str(data["past_diseases"])

    db.commit()


def save_summary(db, session_id: int, data: dict, soap_note: Optional[str] = None):

    summary = db.query(Summary).filter(
        Summary.session_id == session_id
    ).first()

    if not summary:
        summary = Summary(session_id=session_id)
        db.add(summary)

    summary.chief_complaint = data.get("chief_complaint")
    summary.history_present_illness = data.get("history_present_illness")
    summary.past_medical_history = data.get("past_medical_history")
    summary.medications = data.get("medications")
    summary.allergies = data.get("allergies")
    summary.assessment = data.get("assessment")
    if soap_note:
        summary.soap_note = soap_note

    db.commit()
    db.refresh(summary)

    return summary
