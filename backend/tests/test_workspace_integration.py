"""Workspace API integration — real auth, session RBAC, ClinicalContextBuilder."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import create_access_token, get_password_hash
from app.core import config as config_module
from app.models import Session as SessionModel
from app.models import Summary
from app.models.user import User, UserRole
from app.modules.workspace.interface.dto import CONTRACT_VERSION, WorkspacePlanResponse


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
    password: str = "VeryStrongPassword123!",
) -> User:
    user = User(
        email=email,
        full_name=full_name,
        hashed_password=get_password_hash(password),
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
    chief_complaint: str = "Headache for two days",
) -> int:
    session = SessionModel(
        patient_id=patient_id,
        doctor_id=doctor_id,
        initial_complaint=chief_complaint,
    )
    db.add(session)
    await db.flush()
    db.add(
        Summary(
            session_id=session.id,
            chief_complaint=chief_complaint,
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
async def test_unauthenticated_request_returns_401(async_client: AsyncClient) -> None:
    response = await async_client.get("/api/sessions/1/workspace")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_invalid_token_returns_401(async_client: AsyncClient) -> None:
    response = await async_client.get(
        "/api/sessions/1/workspace",
        headers=_auth("not-a-valid-jwt"),
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_patient_forbidden(
    async_client: AsyncClient, db: AsyncSession
) -> None:
    patient = await _create_user(
        db,
        email="ws-patient@test.com",
        full_name="ws_patient",
        role=UserRole.PATIENT,
    )
    session_id = await _create_session_with_summary(db, patient_id=patient.id)

    response = await async_client.get(
        f"/api/sessions/{session_id}/workspace",
        headers=_auth(_token_for(patient)),
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "WORKSPACE_ACCESS_DENIED"


@pytest.mark.asyncio
async def test_doctor_forbidden_other_doctors_session(
    async_client: AsyncClient, db: AsyncSession
) -> None:
    patient = await _create_user(
        db,
        email="ws-patient-b@test.com",
        full_name="ws_patient_b",
        role=UserRole.PATIENT,
    )
    doctor_a = await _create_user(
        db,
        email="ws-doctor-a@test.com",
        full_name="ws_doctor_a",
        role=UserRole.DOCTOR,
    )
    doctor_b = await _create_user(
        db,
        email="ws-doctor-b@test.com",
        full_name="ws_doctor_b",
        role=UserRole.DOCTOR,
    )
    session_id = await _create_session_with_summary(
        db, patient_id=patient.id, doctor_id=doctor_a.id
    )

    response = await async_client.get(
        f"/api/sessions/{session_id}/workspace",
        headers=_auth(_token_for(doctor_b)),
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "WORKSPACE_ACCESS_DENIED"


@pytest.mark.asyncio
async def test_session_not_found_mapped(
    async_client: AsyncClient, db: AsyncSession
) -> None:
    doctor = await _create_user(
        db,
        email="ws-doctor-missing@test.com",
        full_name="ws_doctor_missing",
        role=UserRole.DOCTOR,
    )

    response = await async_client.get(
        "/api/sessions/999999/workspace",
        headers=_auth(_token_for(doctor)),
    )
    # get_authorized_session(not_found_as_403=True) → workspace access denied
    assert response.status_code == 403
    assert response.json()["detail"] == "WORKSPACE_ACCESS_DENIED"


@pytest.mark.asyncio
async def test_successful_workspace_generation(
    async_client: AsyncClient, db: AsyncSession
) -> None:
    patient = await _create_user(
        db,
        email="ws-patient-ok@test.com",
        full_name="ws_patient_ok",
        role=UserRole.PATIENT,
    )
    doctor = await _create_user(
        db,
        email="ws-doctor-ok@test.com",
        full_name="ws_doctor_ok",
        role=UserRole.DOCTOR,
    )
    session_id = await _create_session_with_summary(
        db, patient_id=patient.id, doctor_id=None
    )

    response = await async_client.get(
        f"/api/sessions/{session_id}/workspace",
        headers=_auth(_token_for(doctor)),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    dto = WorkspacePlanResponse.model_validate(body)

    assert dto.session_id == session_id
    assert dto.contract_version == CONTRACT_VERSION == "1.0.0"
    assert response.headers["X-Contract-Version"] == "1.0.0"
    assert response.headers["ETag"] == dto.plan_etag
    assert len(dto.plan_etag) == 64
    assert "decision_trace" not in body


@pytest.mark.asyncio
async def test_successful_trace_with_contract_headers(
    async_client: AsyncClient, db: AsyncSession
) -> None:
    patient = await _create_user(
        db,
        email="ws-patient-trace@test.com",
        full_name="ws_patient_trace",
        role=UserRole.PATIENT,
    )
    doctor = await _create_user(
        db,
        email="ws-doctor-trace@test.com",
        full_name="ws_doctor_trace",
        role=UserRole.DOCTOR,
    )
    session_id = await _create_session_with_summary(
        db, patient_id=patient.id, doctor_id=doctor.id
    )

    response = await async_client.get(
        f"/api/sessions/{session_id}/workspace/trace",
        headers=_auth(_token_for(doctor)),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["session_id"] == session_id
    assert isinstance(body["steps"], list)
    assert response.headers["ETag"] == body["plan_etag"]
    assert response.headers["X-Contract-Version"] == "1.0.0"
