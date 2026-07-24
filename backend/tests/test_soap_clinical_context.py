import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.api.intake as intake_api
from app.models import Intake, Message, Session as DBSession, Summary
from app.models.session import SoapStatus
from app.schemas.intake import (
    ChronicCondition,
    CurrentMedication,
    LabResult,
    MedicalOverview,
)
from app.services.clinical_context_builder import (
    ClinicalContextBuilder,
    format_overview_for_soap_prompt,
)
from app.services.medical_overview_service import overview_for_storage
from app.services.soap_generator import soap_generator
from app.services.soap_task import run_soap_generation
from tests.test_api_integration import VALID_DEMOGRAPHICS
from tests.test_mvp_flow import _national_id_from_seed


async def _register_patient_async(
    client: AsyncClient,
    *,
    seed: str,
    password: str = "VeryStrongPassword123!",
) -> tuple[str, int, str]:
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
    return login.json()["access_token"], patient_id, national_id


def _demographics_for_patient(national_id: str, *, chief_complaint: str = "Chest pain") -> dict:
    return {**VALID_DEMOGRAPHICS, "national_id": national_id, "chief_complaint": chief_complaint}


async def _create_session_with_intake(
    db: AsyncSession,
    client: AsyncClient,
    *,
    token: str,
    patient_id: int,
    national_id: str,
    overview: MedicalOverview,
    clinical: dict | None = None,
    chat_messages: list[tuple[str, str]] | None = None,
) -> int:
    headers = {"Authorization": f"Bearer {token}"}
    session_response = await client.post(
        "/api/chat/session",
        json={"initial_complaint": "Chest pain"},
        headers=headers,
    )
    assert session_response.status_code == 200, session_response.text
    session_id = session_response.json()["id"]

    clinical_payload = clinical or {
        "chief_complaint": "Chest pain",
        "hpi_summary": "Substernal chest pain for 2 days",
        "pertinent_positives": ["radiation to left arm"],
        "pertinent_negatives": ["no fever"],
        "red_flags": ["diaphoresis"],
        "patient_questions": [],
    }

    intake = Intake(
        session_id=session_id,
        current_layer=5,
        demographics_json=json.dumps(
            _demographics_for_patient(
                national_id,
                chief_complaint=clinical_payload["chief_complaint"],
            ),
            ensure_ascii=False,
        ),
        clinical_summary_json=json.dumps(clinical_payload, ensure_ascii=False),
        medical_history_json=json.dumps(overview_for_storage(overview), ensure_ascii=False),
    )
    db.add(intake)
    db.add(
        Summary(
            session_id=session_id,
            chief_complaint=clinical_payload["chief_complaint"],
            history_present_illness=clinical_payload["hpi_summary"],
            is_hpi_complete=True,
        )
    )
    if chat_messages:
        for role, content in chat_messages:
            db.add(Message(session_id=session_id, role=role, content=content))
    await db.commit()
    return session_id


def _mock_soap_llm(monkeypatch, *, content: str, captured: dict | None = None):
    async def fake_openrouter_create(**kwargs):
        if captured is not None:
            captured["messages"] = kwargs["messages"]
        response = MagicMock()
        response.choices = [MagicMock(message=MagicMock(content=content))]
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


class TestClinicalContextBuilderUnit:
    def test_format_overview_for_soap_prompt_includes_sections(self) -> None:
        overview = MedicalOverview(
            allergies="Penicillin",
            surgical_history="Appendectomy",
            family_history="Diabetes",
            chronic_conditions=[
                ChronicCondition(id="c1", name="Hypertension", duration="5 years"),
            ],
            current_medications=[
                CurrentMedication(id="m1", name="Metformin", amount="500mg", frequency="BID"),
            ],
        )
        text = format_overview_for_soap_prompt(overview)
        assert "[Chronic Conditions]" in text
        assert "Hypertension" in text
        assert "[Surgical History]" in text
        assert "Appendectomy" in text
        assert "[Current Medications]" in text
        assert "Metformin" in text

    @pytest.mark.asyncio
    async def test_builder_assembles_immutable_context_with_labs_meds_pmh(
        self,
        async_client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        token, patient_id, national_id = await _register_patient_async(
            async_client, seed="ctx-builder-unit"
        )
        overview = MedicalOverview(
            allergies="Aspirin",
            surgical_history="Cholecystectomy",
            chronic_conditions=[
                ChronicCondition(id="cond-dm", name="Diabetes", duration="10 years"),
            ],
            current_medications=[
                CurrentMedication(id="med-1", name="Lisinopril", amount="10mg", frequency="daily"),
            ],
            lab_results=[
                LabResult(
                    id="lab-1",
                    name="CBC Panel",
                    extracted_data="WBC: 12.5 | HGB: 11.2 | PLT: 180",
                ),
            ],
        )
        session_id = await _create_session_with_intake(
            db,
            async_client,
            token=token,
            patient_id=patient_id,
            national_id=national_id,
            overview=overview,
        )

        ctx = await ClinicalContextBuilder().build(db, session_id)

        assert ctx.session_id == session_id
        assert ctx.patient_id == patient_id
        assert ctx.overview is not None
        assert any(c.name == "Diabetes" for c in ctx.overview.chronic_conditions)
        assert ctx.pmh_context is not None
        assert "Diabetes" in ctx.pmh_context
        assert "Cholecystectomy" in ctx.pmh_context
        assert len(ctx.lab_evidence) == 1
        assert ctx.lab_evidence[0].extracted_data and "WBC: 12.5" in ctx.lab_evidence[0].extracted_data
        assert any(m.name == "Lisinopril" for m in ctx.medication_evidence)
        assert any(a.lab_results for a in ctx.file_analyses)
        assert any(a.medications for a in ctx.file_analyses)
        assert any(a.concept == "Diabetes" for a in ctx.pmh_assertions)
        assert "Red flags" in (ctx.summary.additional_notes or "")

        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ctx.session_id = 999  # type: ignore[misc]


@pytest.mark.asyncio
async def test_soap_includes_lab_ocr_findings(
    async_client: AsyncClient,
    db: AsyncSession,
    monkeypatch,
) -> None:
    token, patient_id, national_id = await _register_patient_async(
        async_client, seed="soap-lab-ocr"
    )
    overview = MedicalOverview(
        lab_results=[
            LabResult(
                id="lab-cbc",
                name="CBC Panel",
                extracted_data="WBC 18.2 elevated, Troponin I 0.42 ng/mL",
            ),
        ],
    )
    session_id = await _create_session_with_intake(
        db,
        async_client,
        token=token,
        patient_id=patient_id,
        national_id=national_id,
        overview=overview,
    )

    captured: dict = {}
    _mock_soap_llm(
        monkeypatch,
        content="# SOAP\n\nO: Labs reviewed\n\n<<<CLINICAL_CONFLICTS>>>[]<<<END_CLINICAL_CONFLICTS>>>",
        captured=captured,
    )

    await run_soap_generation(session_id)

    prompt = captured["messages"][1]["content"]
    assert "=== MEDICAL FILE ANALYSIS ===" in prompt
    assert "CBC Panel" in prompt
    assert "Troponin I 0.42" in prompt


@pytest.mark.asyncio
async def test_soap_includes_medication_evidence(
    async_client: AsyncClient,
    db: AsyncSession,
    monkeypatch,
) -> None:
    token, patient_id, national_id = await _register_patient_async(
        async_client, seed="soap-med-ocr"
    )
    overview = MedicalOverview(
        current_medications=[
            CurrentMedication(
                id="med-atorva",
                name="Atorvastatin",
                amount="40mg",
                frequency="nightly",
            ),
        ],
    )
    session_id = await _create_session_with_intake(
        db,
        async_client,
        token=token,
        patient_id=patient_id,
        national_id=national_id,
        overview=overview,
    )

    captured: dict = {}
    _mock_soap_llm(
        monkeypatch,
        content="# SOAP\n\nS: Meds noted\n\n<<<CLINICAL_CONFLICTS>>>[]<<<END_CLINICAL_CONFLICTS>>>",
        captured=captured,
    )

    await run_soap_generation(session_id)

    prompt = captured["messages"][1]["content"]
    assert "Atorvastatin" in prompt
    assert "=== MEDICAL FILE ANALYSIS ===" in prompt
    assert "Medications:" in prompt


@pytest.mark.asyncio
async def test_soap_includes_pmh_from_overview(
    async_client: AsyncClient,
    db: AsyncSession,
    monkeypatch,
) -> None:
    token, patient_id, national_id = await _register_patient_async(
        async_client, seed="soap-pmh"
    )
    overview = MedicalOverview(
        surgical_history="CABG 2019",
        chronic_conditions=[
            ChronicCondition(id="cond-cad", name="Coronary artery disease", duration="6 years"),
        ],
    )
    session_id = await _create_session_with_intake(
        db,
        async_client,
        token=token,
        patient_id=patient_id,
        national_id=national_id,
        overview=overview,
    )

    captured: dict = {}
    _mock_soap_llm(
        monkeypatch,
        content="# SOAP\n\nS: PMH noted\n\n<<<CLINICAL_CONFLICTS>>>[]<<<END_CLINICAL_CONFLICTS>>>",
        captured=captured,
    )

    await run_soap_generation(session_id)

    prompt = captured["messages"][1]["content"]
    assert "### Patient Past Medical History (From Questionnaire):" in prompt
    assert "Coronary artery disease" in prompt
    assert "CABG 2019" in prompt


@pytest.mark.asyncio
async def test_soap_conflict_detection_with_overview_assertions(
    async_client: AsyncClient,
    db: AsyncSession,
    monkeypatch,
) -> None:
    token, patient_id, national_id = await _register_patient_async(
        async_client, seed="soap-conflict"
    )
    overview = MedicalOverview(
        chronic_conditions=[
            ChronicCondition(id="cond-asthma", name="Asthma", duration="since childhood"),
        ],
    )
    denial_quote = "I have never had asthma"
    session_id = await _create_session_with_intake(
        db,
        async_client,
        token=token,
        patient_id=patient_id,
        national_id=national_id,
        overview=overview,
        chat_messages=[
            ("user", denial_quote),
            ("assistant", "Understood, thank you."),
        ],
    )

    conflict_footer = (
        "<<<CLINICAL_CONFLICTS>>>"
        "["
        '{"pmh_assertion_id":"cond-asthma","chat_polarity":"deny",'
        f'"chat_quote":"{denial_quote}","concept":"Asthma","confidence":"high"'
        "}"
        "]"
        "<<<END_CLINICAL_CONFLICTS>>>"
    )
    _mock_soap_llm(
        monkeypatch,
        content=f"# SOAP\n\nS: Patient denies asthma\n\n{conflict_footer}",
    )

    await run_soap_generation(session_id)

    summary = (
        await db.execute(select(Summary).where(Summary.session_id == session_id))
    ).scalar_one()
    assert summary.soap_note is not None
    assert "Clinical Discrepancy Alert" in summary.soap_note
    assert "Asthma" in summary.soap_note


@pytest.mark.asyncio
async def test_intake_submit_enqueues_soap_generation(
    async_client: AsyncClient,
    db: AsyncSession,
    monkeypatch,
) -> None:
    token, _patient_id, national_id = await _register_patient_async(
        async_client, seed="soap-enqueue"
    )
    headers = {"Authorization": f"Bearer {token}"}

    session_response = await async_client.post(
        "/api/chat/session",
        json={"initial_complaint": "Abdominal pain"},
        headers=headers,
    )
    assert session_response.status_code == 200, session_response.text
    session_id = session_response.json()["id"]

    overview = MedicalOverview(
        allergies="None",
        chronic_conditions=[ChronicCondition(id="c1", name="GERD", duration="1 year")],
        current_medications=[],
    )
    intake = Intake(
        session_id=session_id,
        current_layer=5,
        demographics_json=json.dumps(
            _demographics_for_patient(national_id, chief_complaint="Abdominal pain"),
            ensure_ascii=False,
        ),
        clinical_summary_json=json.dumps(
            {
                "chief_complaint": "Abdominal pain",
                "hpi_summary": "Epigastric pain 3 days",
                "pertinent_positives": [],
                "pertinent_negatives": [],
                "red_flags": [],
                "patient_questions": [],
            }
        ),
        medical_history_json=json.dumps(overview_for_storage(overview)),
    )
    db.add(intake)
    await db.commit()

    triggered: dict = {}

    def fake_trigger(background_tasks, sid: int, **kwargs) -> None:
        triggered["session_id"] = sid
        triggered["kwargs"] = kwargs

    monkeypatch.setattr(intake_api, "trigger_soap_generation", fake_trigger)

    submit = await async_client.post(f"/api/intake/{session_id}/submit", headers=headers)
    assert submit.status_code == 200, submit.text
    assert triggered["session_id"] == session_id

    session = (
        await db.execute(select(DBSession).where(DBSession.id == session_id))
    ).scalar_one()
    assert session.soap_status == SoapStatus.GENERATING


@pytest.mark.asyncio
async def test_chat_only_soap_without_overview_omits_pmh_section(
    async_client: AsyncClient,
    db: AsyncSession,
    monkeypatch,
) -> None:
    """Chat-only path with no overview/PMH should still succeed without PMH section."""
    token, _patient_id, _national_id = await _register_patient_async(
        async_client, seed="soap-chat-only-ctx"
    )
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

    captured: dict = {}
    _mock_soap_llm(
        monkeypatch,
        content=(
            "# SOAP\n\nS: Chest pain\n\nA: Clinical impression\n\nP: Plan\n\n"
            "<<<CLINICAL_CONFLICTS>>>[]<<<END_CLINICAL_CONFLICTS>>>"
        ),
        captured=captured,
    )

    await run_soap_generation(session_id)

    session = (
        await db.execute(select(DBSession).where(DBSession.id == session_id))
    ).scalar_one()
    assert session.soap_status == SoapStatus.READY

    user_prompt = captured["messages"][1]["content"]
    assert "Chest pain" in user_prompt
    assert "### Patient Past Medical History (From Questionnaire):" not in user_prompt
