"""Build patient-owned JSON export bundles (no audit logs / AI telemetry)."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models import Intake, Message, PatientPMH, Session, Summary, User
from app.models.patient_consent import PatientConsent
from app.models.privacy_export_job import PrivacyExportJob, PrivacyExportJobStatus
from app.privacy.consent_service import list_consent_records
from app.services.storage_service import storage_service

logger = logging.getLogger(__name__)

EXPORT_BUNDLE_VERSION = "1.0"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _user_profile(user: User) -> dict[str, Any]:
    return {
        "user_id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "national_id": user.national_id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "age": user.age,
        "sex": user.sex,
        "weight": user.weight,
        "height": user.height,
        "role": user.role.value if hasattr(user.role, "value") else str(user.role),
        "created_at": _iso(user.created_at),
        "phone": None,
        "phone_note": "N/A — users table has no phone column",
    }


def _consent_row(row: PatientConsent) -> dict[str, Any]:
    return {
        "id": row.id,
        "consent_key": row.consent_key,
        "policy_version": row.policy_version,
        "granted": row.granted,
        "granted_at": _iso(row.granted_at),
        "withdrawn_at": _iso(row.withdrawn_at),
        "created_at": _iso(row.created_at),
    }


async def build_export_payload(db: AsyncSession, user_id: int) -> dict[str, Any]:
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise ValueError("user_not_found")

    pmh_result = await db.execute(
        select(PatientPMH).where(PatientPMH.patient_id == user_id)
    )
    pmh = pmh_result.scalar_one_or_none()

    sessions_result = await db.execute(
        select(Session)
        .where(Session.patient_id == user_id)
        .options(
            selectinload(Session.messages),
            selectinload(Session.summary),
            selectinload(Session.intake),
            selectinload(Session.files),
        )
        .order_by(Session.id.asc())
    )
    sessions = list(sessions_result.scalars().unique().all())

    consent_rows = await list_consent_records(db, user_id)

    session_payloads: list[dict[str, Any]] = []
    for sess in sessions:
        messages = [
            {
                "id": m.id,
                "role": m.role.value if hasattr(m.role, "value") else str(m.role),
                "content": m.content,
                "created_at": _iso(m.created_at),
            }
            for m in sorted(sess.messages or [], key=lambda x: x.id)
        ]
        summary_payload = None
        if sess.summary:
            s = sess.summary
            summary_payload = {
                "id": s.id,
                "chief_complaint": s.chief_complaint,
                "history_present_illness": s.history_present_illness,
                "past_medical_history": s.past_medical_history,
                "medications": s.medications,
                "allergies": s.allergies,
                "assessment": s.assessment,
                "is_hpi_complete": s.is_hpi_complete,
                "soap_note": s.soap_note,
                "soap_citations_json": s.soap_citations_json,
                "soap_verification_status": s.soap_verification_status,
                "soap_conflicts_json": s.soap_conflicts_json,
                "legacy_soap_json": s.legacy_soap_json,
                "created_at": _iso(s.created_at),
            }
        intake_payload = None
        if sess.intake:
            i = sess.intake
            intake_payload = {
                "id": i.id,
                "current_layer": i.current_layer,
                "demographics_json": i.demographics_json,
                "hpi_questions_json": i.hpi_questions_json,
                "hpi_answers_json": i.hpi_answers_json,
                "question_strategy": i.question_strategy,
                "clinical_summary_json": i.clinical_summary_json,
                "medical_history_json": i.medical_history_json,
                "llm_fallback_used": i.llm_fallback_used,
                "created_at": _iso(i.created_at),
                "updated_at": _iso(i.updated_at),
            }
        files_payload = [
            {
                "id": f.id,
                "filename": f.filename,
                "size_bytes": f.size_bytes,
                "content_type": f.content_type,
                "condition_id": f.condition_id,
                "created_at": _iso(f.created_at),
            }
            for f in sorted(sess.files or [], key=lambda x: x.id)
        ]
        session_payloads.append(
            {
                "id": sess.id,
                "doctor_id": sess.doctor_id,
                "status": sess.status.value if hasattr(sess.status, "value") else str(sess.status),
                "soap_status": (
                    sess.soap_status.value
                    if hasattr(sess.soap_status, "value")
                    else str(sess.soap_status)
                ),
                "initial_complaint": sess.initial_complaint,
                "created_at": _iso(sess.created_at),
                "updated_at": _iso(sess.updated_at),
                "completed_at": _iso(sess.completed_at),
                "messages": messages,
                "summary": summary_payload,
                "intake": intake_payload,
                "files_metadata": files_payload,
            }
        )

    return {
        "export_version": EXPORT_BUNDLE_VERSION,
        "generated_at": _iso(_utcnow()),
        "subject_user_id": user_id,
        "profile": _user_profile(user),
        "pmh": (
            {
                "patient_id": pmh.patient_id,
                "answers_json": pmh.answers_json,
                "overview_json": pmh.overview_json,
                "last_updated": _iso(pmh.last_updated),
            }
            if pmh
            else None
        ),
        "sessions": session_payloads,
        "consents": [_consent_row(r) for r in consent_rows],
        "excluded_categories": [
            "audit_logs",
            "internal_ai_telemetry",
            "other_patients_data",
            "uploaded_file_binary_content",
        ],
    }


async def create_export_job(db: AsyncSession, user_id: int) -> PrivacyExportJob:
    public_id = str(uuid.uuid4())
    job = PrivacyExportJob(
        public_id=public_id,
        user_id=user_id,
        status=PrivacyExportJobStatus.PENDING,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def run_export_job(job_id: int) -> None:
    """Background worker entry — uses its own DB session."""
    from app.db.database import get_async_session

    async with get_async_session() as db:
        result = await db.execute(
            select(PrivacyExportJob).where(PrivacyExportJob.id == job_id)
        )
        job = result.scalar_one_or_none()
        if job is None:
            logger.warning("privacy export job missing id=%s", job_id)
            return
        if job.status not in (
            PrivacyExportJobStatus.PENDING,
            PrivacyExportJobStatus.PROCESSING,
        ):
            return

        job.status = PrivacyExportJobStatus.PROCESSING
        await db.commit()

        try:
            payload = await build_export_payload(db, job.user_id)
            raw = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            storage_key = f"privacy-exports/{job.user_id}/{job.public_id}.json"
            await storage_service.upload_file(
                storage_key, raw, content_type="application/json; charset=utf-8"
            )
            now = _utcnow()
            ttl_hours = settings.privacy_export_bundle_ttl_hours
            job.storage_key = storage_key
            job.status = PrivacyExportJobStatus.READY
            job.completed_at = now
            job.download_expires_at = now + timedelta(hours=ttl_hours)
            job.error_code = None
            await db.commit()
        except Exception:
            logger.exception("privacy export failed job_id=%s", job.public_id)
            job.status = PrivacyExportJobStatus.FAILED
            job.error_code = "export_failed"
            job.completed_at = _utcnow()
            await db.commit()


async def resolve_download_url(job: PrivacyExportJob) -> Optional[str]:
    if job.status != PrivacyExportJobStatus.READY or not job.storage_key:
        return None
    if job.download_expires_at and _as_utc(job.download_expires_at) < _utcnow():
        return None
    expires = settings.privacy_export_download_url_seconds
    if getattr(storage_service, "is_local", False):
        return f"/api/privacy/export/{job.public_id}/download"
    return await storage_service.get_presigned_url(job.storage_key, expires_in=expires)


async def get_job_for_user(
    db: AsyncSession, *, public_id: str, user_id: int
) -> Optional[PrivacyExportJob]:
    result = await db.execute(
        select(PrivacyExportJob).where(
            PrivacyExportJob.public_id == public_id,
            PrivacyExportJob.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()
