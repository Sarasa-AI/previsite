"""Clinical content API tests — wiring, envelope shape, domain leakage."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.observability.middleware import CorrelationIdMiddleware
from app.main import app as main_app
from app.modules.timeline.domain.enums import (
    ClinicalCategory,
    EventSource,
    EventType,
    TemporalKind,
    TemporalPrecision,
    TemporalStatus,
)
from app.modules.timeline.domain.models import (
    ClinicalTimeline,
    TemporalExpression,
    TimelineEvent,
)
from app.modules.workspace.api import router as workspace_router
from app.modules.workspace.api.dependencies import (
    ClinicalContentInputs,
    resolve_clinical_content_inputs,
)
from app.modules.workspace.application.projections.adapters import (
    ClinicalContentAdapters,
    DemographicsAdapter,
    DocumentAdapterItem,
    SessionAdapter,
    SoapAdapter,
)
from app.modules.workspace.interface.clinical_content_dto import (
    CONTENT_VERSION,
    ClinicalContentResponse,
)
from app.schemas.clinical_context import ClinicalContext, LabEvidence, MedicationEvidence
from app.schemas.intake import CurrentMedication, LabResult, MedicalOverview
from app.schemas.medical import MedicalSummary

FIXED_NOW = datetime(2026, 7, 28, 15, 0, 0, tzinfo=timezone.utc)
SESSION_ID = 42
GENERATED_AT = "2026-07-28T15:00:00+00:00"


def _timeline(*labels: str) -> ClinicalTimeline:
    events = []
    for i, label in enumerate(labels):
        events.append(
            TimelineEvent(
                event_id=f"e{i}",
                event_type=EventType.SYMPTOM_ONGOING,
                clinical_category=ClinicalCategory.SYMPTOM,
                label=label,
                temporal=TemporalExpression(
                    kind=TemporalKind.RELATIVE_DURATION,
                    raw_text="2 days",
                    relative_value=2,
                    relative_unit="days",
                    precision=TemporalPrecision.DAY,
                    uncertainty=False,
                ),
                status=TemporalStatus.ONGOING,
                source=EventSource.HPI,
            )
        )
    return ClinicalTimeline(
        session_id=SESSION_ID,
        patient_id=7,
        anchor_at=FIXED_NOW,
        events=tuple(events),
    )


def _context() -> ClinicalContext:
    return ClinicalContext(
        session_id=SESSION_ID,
        patient_id=7,
        summary=MedicalSummary(
            chief_complaint="Headache for two days",
            symptom_duration="2 days",
            allergies=["Penicillin"],
            additional_notes="Red flags: Chest pain",
            is_hpi_complete=True,
            extracted_at=FIXED_NOW,
        ),
        overview=MedicalOverview(
            allergies="Penicillin",
            current_medications=[
                CurrentMedication(
                    id="m1", name="Metformin", amount="500mg", frequency="BID"
                )
            ],
            lab_results=[
                LabResult(
                    id="l1", name="BMP", extracted_data="Potassium 6.5 mEq/L critical"
                )
            ],
        ),
        lab_evidence=(
            LabEvidence(lab_id="l1", name="BMP", extracted_data="Potassium 6.5 critical"),
        ),
        medication_evidence=(
            MedicationEvidence(
                medication_id="m1", name="Metformin", amount="500mg", frequency="BID"
            ),
        ),
        timeline=_timeline("Headache onset"),
    )


def _adapters() -> ClinicalContentAdapters:
    return ClinicalContentAdapters(
        session=SessionAdapter(
            session_id=SESSION_ID,
            status="active",
            visit_type="Follow-up",
            generated_at=GENERATED_AT,
        ),
        demographics=DemographicsAdapter(
            first_name="Jane",
            last_name="Doe",
            age=54,
            sex="female",
            national_id="MRN-10042",
        ),
        documents=(
            DocumentAdapterItem(
                file_id=10,
                filename="labs.pdf",
                uploaded_at="2026-07-27T10:00:00+00:00",
            ),
        ),
        soap=SoapAdapter(
            soap_note="**A - Assessment**\nMigraine.\n\n**P - Plan**\nNSAID.",
            soap_status="ready",
        ),
    )


def _build_test_app() -> FastAPI:
    test_app = FastAPI()
    test_app.add_middleware(CorrelationIdMiddleware)
    test_app.include_router(workspace_router)
    return test_app


@pytest.fixture
def api_app() -> FastAPI:
    return _build_test_app()


@pytest.fixture
def client(api_app: FastAPI):
    fixed_ctx = _context()
    fixed_adapters = _adapters()

    async def _override(session_id: int) -> ClinicalContentInputs:
        assert session_id == SESSION_ID
        return ClinicalContentInputs(context=fixed_ctx, adapters=fixed_adapters)

    api_app.dependency_overrides[resolve_clinical_content_inputs] = _override
    with TestClient(api_app) as test_client:
        yield test_client
    api_app.dependency_overrides.clear()


@pytest.fixture
def bare_client(api_app: FastAPI):
    api_app.dependency_overrides.clear()
    with TestClient(api_app) as test_client:
        yield test_client
    api_app.dependency_overrides.clear()


def test_clinical_content_route_registered_on_main_app() -> None:
    paths = {route.path for route in main_app.routes if hasattr(route, "path")}
    assert "/api/sessions/{session_id}/clinical-content" in paths


def test_successful_get_clinical_content(client: TestClient) -> None:
    response = client.get(f"/api/sessions/{SESSION_ID}/clinical-content")
    assert response.status_code == 200
    body = response.json()
    dto = ClinicalContentResponse.model_validate(body)
    assert dto.session_id == SESSION_ID
    assert dto.content_version == CONTENT_VERSION
    assert dto.generated_at == GENERATED_AT
    assert dto.content.chief_complaint is not None
    assert dto.content.chief_complaint.title == "Headache for two days"
    assert dto.content.patient_header is not None
    assert dto.content.patient_header.name == "Jane Doe"
    assert "ClinicalContext" not in response.text
    assert "TimelineEvent" not in response.text
    assert "MedicalSummary" not in response.text


def test_clinical_content_envelope_shape(client: TestClient) -> None:
    body = client.get(f"/api/sessions/{SESSION_ID}/clinical-content").json()
    assert set(body.keys()) == {
        "session_id",
        "context_hash",
        "content_version",
        "generated_at",
        "content",
    }
    assert "patient_header" in body["content"]
    assert "chief_complaint" in body["content"]


def test_clinical_content_requires_auth(bare_client: TestClient) -> None:
    response = bare_client.get(f"/api/sessions/{SESSION_ID}/clinical-content")
    assert response.status_code in (401, 403)
