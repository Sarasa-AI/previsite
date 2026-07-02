from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Session as DBSession
from app.models.summary import Summary
from app.models.session import SoapStatus
from app.services.soap_generator import soap_generator
from app.services.soap_task import run_soap_generation
from tests.test_mvp_flow import _national_id_from_seed


async def _register_patient_async(
    client: AsyncClient,
    *,
    seed: str,
    password: str = "VeryStrongPassword123!",
) -> tuple[str, int]:
    national_id = _national_id_from_seed(seed)
    register = await client.post(
        "/api/auth/register",
        json={"national_id": national_id, "password": password, "role": "patient"},
    )
    assert register.status_code == 200, register.text
    patient_id = register.json()["id"]

    login = await client.post(
        "/api/auth/login",
        json={"national_id": national_id, "password": password},
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"], patient_id


@pytest.mark.asyncio
async def test_chat_soap_generation_uses_summary_without_pmh_tree(
    async_client: AsyncClient,
    db: AsyncSession,
    monkeypatch,
) -> None:
    token, _patient_id = await _register_patient_async(async_client, seed="soap-e2e-patient")
    headers = {"Authorization": f"Bearer {token}"}

    session_response = await async_client.post(
        "/api/chat/session",
        json={"initial_complaint": "Chest pain"},
        headers=headers,
    )
    assert session_response.status_code == 200, session_response.text
    session_id = session_response.json()["id"]

    db.add(
        Summary(
            session_id=session_id,
            chief_complaint="Chest pain",
            history_present_illness="Substernal chest pain for 2 days",
            is_hpi_complete=True,
        )
    )
    await db.commit()

    captured_messages: dict = {}

    async def fake_openrouter_create(**kwargs):
        captured_messages["messages"] = kwargs["messages"]
        response = MagicMock()
        response.choices = [
            MagicMock(
                message=MagicMock(
                    content=(
                        "# SOAP\n\nS: Chest pain\n\nA: Clinical impression\n\nP: Plan\n\n"
                        "<<<CLINICAL_CONFLICTS>>>[]<<<END_CLINICAL_CONFLICTS>>>"
                    )
                )
            )
        ]
        return response

    monkeypatch.setattr(soap_generator, "openrouter_client", MagicMock())
    soap_generator.openrouter_client.chat.completions.create = AsyncMock(
        side_effect=fake_openrouter_create
    )
    monkeypatch.setattr(
        soap_generator.rag_service,
        "search_similar_knowledge",
        AsyncMock(return_value=[]),
    )

    await run_soap_generation(session_id)

    session = (
        await db.execute(select(DBSession).where(DBSession.id == session_id))
    ).scalar_one()
    assert session.soap_status == SoapStatus.READY

    user_prompt = captured_messages["messages"][1]["content"]
    assert "Chest pain" in user_prompt
    assert "### Patient Past Medical History (From Questionnaire):" not in user_prompt

    summary = (
        await db.execute(select(Summary).where(Summary.session_id == session_id))
    ).scalar_one()
    assert summary.legacy_soap_json is not None
    assert summary.soap_note is not None
