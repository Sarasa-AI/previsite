from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Summary
from app.models import Session as DBSession


async def save_summary(
    db: AsyncSession,
    session_id: int,
    data: dict,
    soap_note: Optional[str] = None,
):
    result = await db.execute(
        select(Summary).where(Summary.session_id == session_id)
    )
    summary = result.scalar_one_or_none()

    if not summary:
        session_result = await db.execute(
            select(DBSession).where(DBSession.id == session_id)
        )
        session = session_result.scalar_one_or_none()
        summary = Summary(
            session_id=session_id,
            organization_id=session.organization_id if session else None,
        )
        db.add(summary)

    summary.chief_complaint = data.get("chief_complaint")
    summary.history_present_illness = data.get("history_present_illness")
    summary.past_medical_history = data.get("past_medical_history")
    summary.medications = data.get("medications")
    summary.allergies = data.get("allergies")
    summary.assessment = data.get("assessment")
    summary.is_hpi_complete = data.get("is_hpi_complete", False)
    if soap_note:
        summary.soap_note = soap_note

    await db.commit()
    await db.refresh(summary)

    return summary
