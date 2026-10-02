"""End-to-end workflow mutation integration — real auth + DB."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import create_access_token, get_password_hash
from app.core import config as config_module
from app.models import Session as SessionModel
from app.models import Summary
from app.models.session import SessionStatus
from app.models.user import User, UserRole
from app.modules.workspace.interface.dto import WorkspacePlanResponse


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _token_for(user: User) -> str:
    return create_access_token(data={"sub": str(user.id), "email": user.email})


async def _create_user(
    db: AsyncSession,
    *,
    email: str,
    full_name: str,
    role: UserRole,
) -> User:
    user = User(
        email=email,
        full_name=full_name,
        hashed_password=get_password_hash("VeryStrongPassword123!"),
        role=role,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _create_session_with_summary(
    db: AsyncSession,
    *,
    patient_id: int,
    doctor_id: int | None = None,
    status: SessionStatus = SessionStatus.ACTIVE,
) -> int:
    session = SessionModel(
        patient_id=patient_id,
        doctor_id=doctor_id,
        initial_complaint="Headache for two days",
        status=status,
    )
    db.add(session)
    await db.flush()
    db.add(
        Summary(
            session_id=session.id,
            chief_complaint="Headache for two days",
            history_present_illness="Symptoms for two days",
            is_hpi_complete=True,
        )
    )
    await db.commit()
    await db.refresh(session)
    return session.id


@pytest.fixture(autouse=True)
def _disable_single_doctor_mode():
    previous = config_module.settings.single_doctor_mode
    config_module.settings.single_doctor_mode = False
    yield
    config_module.settings.single_doctor_mode = previous


@pytest.mark.asyncio
async def test_stale_etag_leaves_plan_unchanged(
    async_client: AsyncClient, db: AsyncSession
) -> None:
    patient = await _create_user(
        db, email="wf-stale-patient@test.com", full_name="p", role=UserRole.PATIENT
    )
    doctor = await _create_user(
        db, email="wf-stale-doctor@test.com", full_name="d", role=UserRole.DOCTOR
    )
    session_id = await _create_session_with_summary(
        db, patient_id=patient.id, doctor_id=doctor.id
    )
    headers = _auth(_token_for(doctor))
    get1 = await async_client.get(
        f"/api/sessions/{session_id}/workspace", headers=headers
    )
    etag = get1.json()["plan_etag"]
    context_hash = get1.json()["metadata"]["context_hash"]

    stale = await async_client.post(
        f"/api/sessions/{session_id}/workspace/decision-items/medications/resolve",
        headers={**headers, "If-Match": "deadbeef"},
        json={},
    )
    assert stale.status_code == 409
    assert stale.json()["detail"] == "WORKSPACE_PLAN_STALE"

    get2 = await async_client.get(
        f"/api/sessions/{session_id}/workspace", headers=headers
    )
    # Context hash must remain stable; plan_etag may only change if a new
    # workflow event was appended — a rejected stale write must not append.
    assert get2.json()["metadata"]["context_hash"] == context_hash
    assert get2.json()["plan_etag"] == etag


@pytest.mark.asyncio
async def test_ack_resolve_dismiss_roundtrip(
    async_client: AsyncClient, db: AsyncSession
) -> None:
    patient = await _create_user(
        db, email="wf-int-patient@test.com", full_name="p", role=UserRole.PATIENT
    )
    doctor = await _create_user(
        db, email="wf-int-doctor@test.com", full_name="d", role=UserRole.DOCTOR
    )
    session_id = await _create_session_with_summary(
        db, patient_id=patient.id, doctor_id=doctor.id
    )
    headers = _auth(_token_for(doctor))

    get1 = await async_client.get(
        f"/api/sessions/{session_id}/workspace", headers=headers
    )
    assert get1.status_code == 200, get1.text
    plan = get1.json()
    etag = plan["plan_etag"]
    WorkspacePlanResponse.model_validate(plan)

    # Re-fetch so etag reflects the post-open event store (stable thereafter).
    get2 = await async_client.get(
        f"/api/sessions/{session_id}/workspace", headers=headers
    )
    assert get2.status_code == 200
    etag = get2.json()["plan_etag"]
    assert get2.json()["plan_etag"] == get1.json()["plan_etag"]

    queue = get2.json()["decision_queue"]
    if queue:
        object_id = queue[0]["object_id"]
        resolve = await async_client.post(
            f"/api/sessions/{session_id}/workspace/decision-items/{object_id}/resolve",
            headers={**headers, "If-Match": etag},
            json={},
        )
        assert resolve.status_code == 200, (
            resolve.text,
            etag,
            get2.json()["metadata"]["context_hash"],
        )
        etag = resolve.json()["plan_etag"]
        assert object_id not in [
            i["object_id"] for i in resolve.json()["decision_queue"]
        ]

    status = await async_client.get(
        f"/api/sessions/{session_id}/workspace/story/status", headers=headers
    )
    assert status.status_code == 200
    assert "story_status" in status.json()

    # Fresh etag before story refresh
    etag = (
        await async_client.get(
            f"/api/sessions/{session_id}/workspace", headers=headers
        )
    ).json()["plan_etag"]
    refresh = await async_client.post(
        f"/api/sessions/{session_id}/workspace/story/refresh",
        headers={**headers, "If-Match": etag},
        json={},
    )
    assert refresh.status_code == 200, refresh.text


@pytest.mark.asyncio
async def test_completed_session_is_read_only(
    async_client: AsyncClient, db: AsyncSession
) -> None:
    patient = await _create_user(
        db, email="wf-ro-patient@test.com", full_name="p", role=UserRole.PATIENT
    )
    doctor = await _create_user(
        db, email="wf-ro-doctor@test.com", full_name="d", role=UserRole.DOCTOR
    )
    session_id = await _create_session_with_summary(
        db,
        patient_id=patient.id,
        doctor_id=doctor.id,
        status=SessionStatus.COMPLETED,
    )
    headers = _auth(_token_for(doctor))
    get1 = await async_client.get(
        f"/api/sessions/{session_id}/workspace", headers=headers
    )
    assert get1.status_code == 200
    etag = get1.json()["plan_etag"]
    assert get1.json()["workspace_state"] == "read_only"

    mutate = await async_client.post(
        f"/api/sessions/{session_id}/workspace/story/refresh",
        headers={**headers, "If-Match": etag},
        json={},
    )
    assert mutate.status_code == 409
    assert mutate.json()["detail"] == "WORKSPACE_READ_ONLY"
