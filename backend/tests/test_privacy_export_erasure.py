"""P2-A Task 7 — patient data export and account erasure."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import create_access_token, get_password_hash, verify_password
from app.core import config as config_module
from app.models import Message, Session, Summary, User
from app.models.message import MessageRole
from app.models.user import UserRole
from app.models.account_deletion_request import (
    AccountDeletionRequest,
    DeletionRequestStatus,
)
from app.models.audit_log import AuditLog
from app.models.pmh import PatientPMH
from app.models.privacy_export_job import PrivacyExportJob, PrivacyExportJobStatus
from app.modules.intelligence.infrastructure.models import ClinicalFindingRecord
from app.privacy.erasure_service import execute_approved_deletion
from app.privacy.export_service import run_export_job
from app.services.audit_service import (
    AUDIT_PRIVACY_EXPORT_REQUEST,
    record_audit,
)
from tests.test_api_integration import _auth_headers, _national_id_from_seed


async def _create_patient(
    db: AsyncSession, *, seed: str, password: str = "PatientPass123!"
) -> User:
    national_id = _national_id_from_seed(seed)
    user = User(
        email=f"privacy_{national_id}@patient.local",
        hashed_password=get_password_hash(password),
        full_name=f"بیمار {national_id[-4:]}",
        national_id=national_id,
        first_name="Ali",
        last_name="Test",
        age=40,
        role=UserRole.PATIENT,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def _patient_headers(user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user.id), "email": user.email})
    return _auth_headers(token)


async def _create_admin(db: AsyncSession) -> User:
    admin = User(
        email="privacy_admin@clinic.local",
        hashed_password=get_password_hash("AdminPass123!"),
        full_name="Privacy Admin",
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(admin)
    await db.commit()
    await db.refresh(admin)
    return admin


async def _seed_clinical_data(db: AsyncSession, patient: User) -> Session:
    sess = Session(patient_id=patient.id, initial_complaint="headache")
    db.add(sess)
    await db.commit()
    await db.refresh(sess)
    db.add(
        Message(
            session_id=sess.id,
            role=MessageRole.USER,
            content="Secret symptom text",
        )
    )
    db.add(
        Summary(
            session_id=sess.id,
            chief_complaint="CC",
            history_present_illness="HPI detail",
        )
    )
    db.add(
        PatientPMH(
            patient_id=patient.id,
            answers_json={"condition": "diabetes"},
            overview_json={"note": "PMH detail"},
        )
    )
    db.add(
        ClinicalFindingRecord(
            finding_id=f"find-{sess.id}",
            session_id=sess.id,
            category="lab",
            severity="moderate",
            title="AI finding",
            summary="telemetry must not export",
            source="test",
        )
    )
    await record_audit(
        db,
        action="intake_read",
        user_id=patient.id,
        resource_type="session",
        resource_id=sess.id,
    )
    await db.commit()
    return sess


@pytest.mark.asyncio
async def test_export_includes_patient_data_and_excludes_telemetry(
    async_client: AsyncClient, db: AsyncSession
) -> None:
    patient = await _create_patient(db, seed="export_a")
    other = await _create_patient(db, seed="export_b")
    await _seed_clinical_data(db, patient)
    await _seed_clinical_data(db, other)
    headers = _patient_headers(patient)

    create = await async_client.post("/api/privacy/export", headers=headers)
    assert create.status_code == 200, create.text
    job_id = create.json()["job_id"]

    job_row = await db.execute(
        select(PrivacyExportJob).where(PrivacyExportJob.public_id == job_id)
    )
    job = job_row.scalar_one()
    await run_export_job(job.id)

    status_resp = await async_client.get(
        f"/api/privacy/export/{job_id}", headers=headers
    )
    assert status_resp.status_code == 200
    body = status_resp.json()
    assert body["status"] == PrivacyExportJobStatus.READY
    assert body["download_url"] is not None

    download = await async_client.get(
        f"/api/privacy/export/{job_id}/download", headers=headers
    )
    assert download.status_code == 200
    bundle = download.json()

    assert bundle["subject_user_id"] == patient.id
    assert bundle["profile"]["email"] == patient.email
    assert bundle["profile"]["phone"] is None
    assert "audit_logs" in bundle["excluded_categories"]
    assert len(bundle["sessions"]) == 1
    assert bundle["sessions"][0]["messages"][0]["content"] == "Secret symptom text"
    assert bundle["pmh"]["answers_json"]["condition"] == "diabetes"
    assert "internal_ai_telemetry" in bundle["excluded_categories"]
    assert "ClinicalFindingRecord" not in json.dumps(bundle)
    assert "telemetry must not export" not in json.dumps(bundle)

    audit_count = await db.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(AuditLog.action == AUDIT_PRIVACY_EXPORT_REQUEST)
    )
    assert audit_count >= 1


@pytest.mark.asyncio
async def test_erasure_anonymizes_and_clears_clinical_other_patient_untouched(
    async_client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config_module.settings, "account_deletion_cool_off_hours", 0)
    patient = await _create_patient(db, seed="erase_a", password="EraseMe123!")
    victim_id = patient.id
    other = await _create_patient(db, seed="erase_b")
    await _seed_clinical_data(db, patient)
    other_sess = await _seed_clinical_data(db, other)
    headers = _patient_headers(patient)
    admin = await _create_admin(db)
    admin_headers = _patient_headers(admin)

    req = await async_client.post(
        "/api/privacy/deletion-request",
        headers=headers,
        json={"password": "EraseMe123!"},
    )
    assert req.status_code == 200, req.text
    request_id = req.json()["id"]

    bad_approve = await async_client.post(
        f"/api/admin/privacy/deletion/{request_id}/approve",
        headers=admin_headers,
    )
    assert bad_approve.status_code == 200

    user_id = await execute_approved_deletion(db, request_id)
    assert user_id == victim_id

    await db.refresh(patient)
    assert patient.email == f"deleted+{victim_id}@anonymized.invalid"
    assert patient.full_name == "Deleted User"
    assert patient.national_id.startswith("D")
    assert patient.is_active is False
    assert not verify_password("EraseMe123!", patient.hashed_password)

    victim_sess_id = (
        await db.execute(select(Session.id).where(Session.patient_id == victim_id))
    ).scalar_one()
    msg = await db.execute(select(Message).where(Message.session_id == victim_sess_id))
    assert msg.scalar_one_or_none() is None

    pmh = await db.get(PatientPMH, victim_id)
    assert pmh is not None
    assert pmh.answers_json == {}
    assert pmh.overview_json == {}

    finding_count = await db.scalar(select(func.count()).select_from(ClinicalFindingRecord))
    assert finding_count == 1

    other_msg = (
        await db.execute(
            select(Message).join(Session).where(Session.patient_id == other.id)
        )
    ).scalar_one_or_none()
    assert other_msg is not None
    assert other_msg.content == "Secret symptom text"

    audit_rows = await db.scalar(select(func.count()).select_from(AuditLog))
    assert audit_rows >= 1


@pytest.mark.asyncio
async def test_deletion_cool_off_blocks_admin_approve(
    async_client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config_module.settings, "account_deletion_cool_off_hours", 72)
    patient = await _create_patient(db, seed="cooloff", password="CoolOff123!")
    headers = _patient_headers(patient)
    admin = await _create_admin(db)
    admin_headers = _patient_headers(admin)

    req = await async_client.post(
        "/api/privacy/deletion-request",
        headers=headers,
        json={"password": "CoolOff123!"},
    )
    assert req.status_code == 200
    request_id = req.json()["id"]

    approve = await async_client.post(
        f"/api/admin/privacy/deletion/{request_id}/approve",
        headers=admin_headers,
    )
    assert approve.status_code == 409
    assert approve.json()["detail"]["code"] == "COOL_OFF_NOT_ELAPSED"

    row = await db.get(AccountDeletionRequest, request_id)
    assert row.status == DeletionRequestStatus.PENDING_COOL_OFF


@pytest.mark.asyncio
async def test_operator_script_executes_approved_request(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config_module.settings, "account_deletion_cool_off_hours", 0)
    patient = await _create_patient(db, seed="script_run", password="Script123!")
    await _seed_clinical_data(db, patient)
    from app.privacy.erasure_service import approve_deletion_request, create_deletion_request

    admin = await _create_admin(db)
    row = await create_deletion_request(db, patient.id)
    await approve_deletion_request(db, row.id, admin.id)

    backend_root = Path(__file__).resolve().parents[1]
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))
    from scripts.execute_account_deletion import _async_main

    code = await _async_main(row.id)
    assert code == 0

    patient_after = (
        await db.execute(select(User.full_name).where(User.id == patient.id))
    ).scalar_one()
    assert patient_after == "Deleted User"
    status_after = (
        await db.execute(
            select(AccountDeletionRequest.status).where(
                AccountDeletionRequest.id == row.id
            )
        )
    ).scalar_one()
    assert status_after == DeletionRequestStatus.COMPLETED
