"""Account erasure — anonymize identity, purge clinical free text and files.

Audit logs are never deleted. Product owner must confirm LEGAL_RETENTION_* defaults.
Phone column: N/A on users — not collected.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import (
    Encounter,
    FamilyGroup,
    FamilyMember,
    File,
    Intake,
    Message,
    PatientPMH,
    PatientProfile,
    Session,
    Summary,
    User,
)
from app.models.account_deletion_request import (
    AccountDeletionRequest,
    DeletionRequestStatus,
)
from app.models.document_artifact import DocumentArtifact
from app.models.mfa_setup_challenge import MfaSetupChallenge
from app.models.patient_consent import PatientConsent
from app.models.refresh_token import RefreshToken
from app.modules.intelligence.infrastructure.models import (
    ClinicalFindingRecord,
    RecommendationRecord,
    RiskSignalRecord,
)
from app.modules.workspace.infrastructure.models import WorkflowEventRecord
from app.auth.security import get_password_hash
from app.services.storage_service import storage_service

logger = logging.getLogger(__name__)

_ERASED_PASSWORD_PLACEHOLDER = get_password_hash("account-erased-not-loginable")

_EMPTY_JSON = "{}"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def anonymized_email(user_id: int) -> str:
    return f"deleted+{user_id}@anonymized.invalid"


def anonymized_national_id(user_id: int) -> str:
    """Fit users.national_id String(10) unique constraint."""
    suffix = str(user_id).zfill(7)[-7:]
    return f"D{suffix}"


async def create_deletion_request(
    db: AsyncSession, user_id: int
) -> AccountDeletionRequest:
    active = await db.execute(
        select(AccountDeletionRequest).where(
            AccountDeletionRequest.user_id == user_id,
            AccountDeletionRequest.status.in_(
                (
                    DeletionRequestStatus.PENDING_COOL_OFF,
                    DeletionRequestStatus.APPROVED,
                )
            ),
        )
    )
    if active.scalar_one_or_none() is not None:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "DELETION_REQUEST_ACTIVE"},
        )

    now = _utcnow()
    cool_off = now + settings.account_deletion_cool_off_timedelta()
    row = AccountDeletionRequest(
        user_id=user_id,
        status=DeletionRequestStatus.PENDING_COOL_OFF,
        requested_at=now,
        cool_off_until=cool_off,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def cancel_deletion_request(
    db: AsyncSession, user_id: int
) -> AccountDeletionRequest:
    from fastapi import HTTPException, status

    result = await db.execute(
        select(AccountDeletionRequest).where(
            AccountDeletionRequest.user_id == user_id,
            AccountDeletionRequest.status == DeletionRequestStatus.PENDING_COOL_OFF,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NO_PENDING_DELETION"},
        )
    row.status = DeletionRequestStatus.CANCELLED
    row.cancelled_at = _utcnow()
    await db.commit()
    await db.refresh(row)
    return row


async def approve_deletion_request(
    db: AsyncSession, request_id: int, admin_user_id: int
) -> AccountDeletionRequest:
    from fastapi import HTTPException, status

    result = await db.execute(
        select(AccountDeletionRequest).where(AccountDeletionRequest.id == request_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if row.status != DeletionRequestStatus.PENDING_COOL_OFF:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "INVALID_DELETION_STATE", "status": row.status},
        )
    now = _utcnow()
    if _as_utc(row.cool_off_until) > now:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "COOL_OFF_NOT_ELAPSED"},
        )
    row.status = DeletionRequestStatus.APPROVED
    row.approved_at = now
    row.approved_by_user_id = admin_user_id
    await db.commit()
    await db.refresh(row)
    return row


async def execute_approved_deletion(
    db: AsyncSession, request_id: int
) -> Optional[int]:
    """Run erasure for one admin-approved request. Returns user_id or None."""
    result = await db.execute(
        select(AccountDeletionRequest).where(AccountDeletionRequest.id == request_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        logger.warning("deletion request missing id=%s", request_id)
        return None
    if row.status != DeletionRequestStatus.APPROVED:
        logger.info(
            "skip deletion id=%s status=%s", request_id, row.status
        )
        return None
    user_id = row.user_id
    await _erase_patient_data(db, user_id)
    row.status = DeletionRequestStatus.COMPLETED
    row.completed_at = _utcnow()
    await db.commit()
    return user_id


async def execute_all_approved_deletions(db: AsyncSession) -> list[int]:
    result = await db.execute(
        select(AccountDeletionRequest.id).where(
            AccountDeletionRequest.status == DeletionRequestStatus.APPROVED
        )
    )
    ids = [r[0] for r in result.all()]
    completed: list[int] = []
    for req_id in ids:
        uid = await execute_approved_deletion(db, req_id)
        if uid is not None:
            completed.append(uid)
    return completed


async def _erase_encounters_and_family(db: AsyncSession, user_id: int) -> None:
    """Mirror session-shell retention onto Encounter; soft-delete owned family."""
    now = _utcnow()

    groups_result = await db.execute(
        select(FamilyGroup).where(FamilyGroup.owner_user_id == user_id)
    )
    groups = list(groups_result.scalars().all())
    group_ids = [g.id for g in groups]

    member_ids: list = []
    if group_ids:
        members_result = await db.execute(
            select(FamilyMember).where(FamilyMember.family_group_id.in_(group_ids))
        )
        members = list(members_result.scalars().all())
        member_ids = [m.id for m in members]
        for m in members:
            if m.deleted_at is None:
                m.deleted_at = now
        for g in groups:
            if g.deleted_at is None:
                g.deleted_at = now

    encounter_filters = [
        Encounter.subject_user_id == user_id,
        Encounter.initiated_by_user_id == user_id,
        Encounter.consent_user_id == user_id,
    ]
    if member_ids:
        encounter_filters.append(Encounter.subject_family_member_id.in_(member_ids))

    enc_result = await db.execute(select(Encounter).where(or_(*encounter_filters)))
    encounters = list(enc_result.scalars().all())

    if settings.legal_retention_keep_session_shell:
        for enc in encounters:
            enc.chief_complaint = None
            enc.consent_snapshot = None
    else:
        for enc in encounters:
            if enc.deleted_at is None:
                enc.deleted_at = now

    profile_result = await db.execute(
        select(PatientProfile).where(PatientProfile.user_id == user_id)
    )
    profile = profile_result.scalar_one_or_none()
    if profile is not None and profile.deleted_at is None:
        profile.deleted_at = now


async def _erase_patient_data(db: AsyncSession, user_id: int) -> None:
    sessions_result = await db.execute(
        select(Session.id).where(Session.patient_id == user_id)
    )
    session_ids = [r[0] for r in sessions_result.all()]

    files: list[File] = []
    if session_ids:
        files_result = await db.execute(
            select(File).where(File.session_id.in_(session_ids))
        )
        files = list(files_result.scalars().all())

    for f in files:
        try:
            await storage_service.delete_file(f.s3_key)
        except Exception:
            logger.exception("failed to delete storage key=%s", f.s3_key)

    if session_ids:
        await db.execute(
            delete(DocumentArtifact).where(
                DocumentArtifact.session_id.in_(session_ids)
            )
        )
        await db.execute(
            delete(ClinicalFindingRecord).where(
                ClinicalFindingRecord.session_id.in_(session_ids)
            )
        )
        await db.execute(
            delete(RiskSignalRecord).where(
                RiskSignalRecord.session_id.in_(session_ids)
            )
        )
        await db.execute(
            delete(RecommendationRecord).where(
                RecommendationRecord.session_id.in_(session_ids)
            )
        )
        await db.execute(
            delete(WorkflowEventRecord).where(
                WorkflowEventRecord.session_id.in_(session_ids)
            )
        )
        await db.execute(delete(Message).where(Message.session_id.in_(session_ids)))
        await db.execute(delete(File).where(File.session_id.in_(session_ids)))
        await db.execute(delete(Summary).where(Summary.session_id.in_(session_ids)))
        await db.execute(delete(Intake).where(Intake.session_id.in_(session_ids)))

        if settings.legal_retention_keep_session_shell:
            await db.execute(
                update(Session)
                .where(Session.id.in_(session_ids))
                .values(
                    initial_complaint=None,
                    soap_error_detail=None,
                )
            )
        else:
            await db.execute(delete(Session).where(Session.id.in_(session_ids)))

    await _erase_encounters_and_family(db, user_id)

    pmh_result = await db.execute(
        select(PatientPMH).where(PatientPMH.patient_id == user_id)
    )
    pmh = pmh_result.scalar_one_or_none()
    if pmh is not None:
        if settings.legal_retention_keep_pmh_shell:
            pmh.answers_json = {}
            pmh.overview_json = {}
        else:
            await db.execute(
                delete(PatientPMH).where(PatientPMH.patient_id == user_id)
            )

    await db.execute(
        update(PatientConsent)
        .where(PatientConsent.user_id == user_id)
        .values(ip=None, user_agent=None)
    )

    await db.execute(delete(RefreshToken).where(RefreshToken.user_id == user_id))
    await db.execute(
        delete(MfaSetupChallenge).where(MfaSetupChallenge.user_id == user_id)
    )

    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if user is not None:
        user.email = anonymized_email(user_id)
        user.full_name = "Deleted User"
        user.national_id = anonymized_national_id(user_id)
        user.first_name = "Deleted"
        user.last_name = "User"
        user.age = None
        user.sex = None
        user.weight = None
        user.height = None
        user.phone = None
        user.hashed_password = _ERASED_PASSWORD_PLACEHOLDER
        user.is_active = False
        user.mfa_secret = None
        user.mfa_enabled = False
        user.mfa_backup_codes_hash = None

    await db.flush()
