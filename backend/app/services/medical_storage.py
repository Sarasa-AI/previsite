from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Summary


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
        summary = Summary(session_id=session_id)
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
