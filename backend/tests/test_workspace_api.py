"""Workspace API layer tests — wiring, DTO serialization, error mapping, OpenAPI."""

from __future__ import annotations

import ast
import inspect
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.observability.middleware import CORRELATION_HEADER, CorrelationIdMiddleware
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
    AuthorizedWorkspaceSession,
    get_generate_workspace_use_case,
    get_trace_enabled,
    get_workflow_event_service,
    resolve_authorized_workspace_mutate,
    resolve_authorized_workspace_read,
    resolve_clinical_context,
)
from app.modules.workspace.api.errors import (
    WorkspaceSessionNotFound,
    map_workspace_error,
)
from app.modules.workspace.application.generate_workspace import GenerateWorkspaceUseCase
from app.modules.workspace.application.workflow.in_memory import (
    InMemoryWorkflowEventRepository,
)
from app.modules.workspace.application.workflow.service import WorkflowEventService
from app.modules.workspace.interface.dto import (
    CONTRACT_VERSION,
    DecisionTraceResponse,
    WorkspacePlanResponse,
)
from app.schemas.clinical_context import (
    ClinicalContext,
    LabEvidence,
    MedicationEvidence,
)
from app.schemas.intake import CurrentMedication, LabResult, MedicalOverview
from app.schemas.medical import MedicalSummary

FIXED_NOW = datetime(2026, 7, 28, 15, 0, 0, tzinfo=timezone.utc)
SESSION_ID = 42


class _FakeUser:
    id = 7
    email = "doctor@test.com"


class _FakeSession:
    id = SESSION_ID
    status = "active"
    soap_status = "pending"


def _fake_auth(session_id: int = SESSION_ID) -> AuthorizedWorkspaceSession:
    session = _FakeSession()
    session.id = session_id
    return AuthorizedWorkspaceSession(session=session, user=_FakeUser(), db=MagicMock())


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


def _context(session_id: int = SESSION_ID) -> ClinicalContext:
    return ClinicalContext(
        session_id=session_id,
        patient_id=7,
        summary=MedicalSummary(
            chief_complaint="Headache for two days",
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
        medication_evidence=(MedicationEvidence(medication_id="m1", name="Metformin"),),
        timeline=_timeline("Headache onset", "Nausea"),
    )


def _build_test_app() -> FastAPI:
    """Minimal app: workspace router + correlation middleware; no DB lifespan."""
    test_app = FastAPI()
    test_app.add_middleware(CorrelationIdMiddleware)
    test_app.include_router(workspace_router)
    return test_app


@pytest.fixture
def api_app() -> FastAPI:
    return _build_test_app()


@pytest.fixture
def client(api_app: FastAPI):
    fixed = _context()
    memory_repo = InMemoryWorkflowEventRepository()
    workflow = WorkflowEventService(memory_repo)

    async def _override_resolve(session_id: int) -> ClinicalContext:
        assert session_id == fixed.session_id
        return fixed

    async def _override_auth_read(session_id: int) -> AuthorizedWorkspaceSession:
        assert session_id == fixed.session_id
        return _fake_auth(session_id)

    async def _override_auth_mutate(session_id: int) -> AuthorizedWorkspaceSession:
        assert session_id == fixed.session_id
        return _fake_auth(session_id)

    api_app.dependency_overrides[resolve_clinical_context] = _override_resolve
    api_app.dependency_overrides[resolve_authorized_workspace_read] = _override_auth_read
    api_app.dependency_overrides[resolve_authorized_workspace_mutate] = (
        _override_auth_mutate
    )
    api_app.dependency_overrides[get_workflow_event_service] = lambda: workflow
    with TestClient(api_app) as test_client:
        yield test_client
    api_app.dependency_overrides.clear()


@pytest.fixture
def bare_client(api_app: FastAPI):
    """Client with no context override (auth required on workspace routes)."""
    api_app.dependency_overrides.clear()
    with TestClient(api_app) as test_client:
        yield test_client
    api_app.dependency_overrides.clear()


def test_route_registration_on_main_app() -> None:
    paths = {route.path for route in main_app.routes if hasattr(route, "path")}
    assert "/api/sessions/{session_id}/workspace" in paths
    assert "/api/sessions/{session_id}/workspace/trace" in paths
    assert "/api/sessions/{session_id}/clinical-content" in paths
    assert "/api/sessions/{session_id}/workspace/acknowledgements" in paths
    assert (
        "/api/sessions/{session_id}/workspace/decision-items/{object_id}/resolve"
        in paths
    )
    assert (
        "/api/sessions/{session_id}/workspace/decision-items/{object_id}/dismiss"
        in paths
    )
    assert "/api/sessions/{session_id}/workspace/story/refresh" in paths
    assert "/api/sessions/{session_id}/workspace/story/status" in paths


def test_successful_get_workspace(client: TestClient) -> None:
    response = client.get(f"/api/sessions/{SESSION_ID}/workspace")
    assert response.status_code == 200
    body = response.json()
    dto = WorkspacePlanResponse.model_validate(body)
    assert dto.contract_version == CONTRACT_VERSION == "1.0.0"
    assert dto.session_id == SESSION_ID
    assert "decision_trace" not in body
    assert response.headers["ETag"] == dto.plan_etag
    assert response.headers["X-Contract-Version"] == "1.0.0"


def test_successful_get_trace(client: TestClient) -> None:
    response = client.get(f"/api/sessions/{SESSION_ID}/workspace/trace")
    assert response.status_code == 200
    dto = DecisionTraceResponse.model_validate(response.json())
    assert dto.session_id == SESSION_ID
    assert isinstance(dto.steps, list)
    assert response.headers["ETag"] == dto.plan_etag
    assert response.headers["X-Contract-Version"] == "1.0.0"


def test_validation_non_int_session_id(client: TestClient) -> None:
    response = client.get("/api/sessions/not-an-id/workspace")
    assert response.status_code == 422


def test_validation_unknown_lens(client: TestClient) -> None:
    response = client.get(
        f"/api/sessions/{SESSION_ID}/workspace",
        params={"lens": "not_a_real_lens"},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "WORKSPACE_LENS_UNKNOWN"


def test_validation_unknown_role(client: TestClient) -> None:
    response = client.get(
        f"/api/sessions/{SESSION_ID}/workspace",
        params={"role": "not_a_real_role"},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "WORKSPACE_ROLE_UNKNOWN"


def test_unauthenticated_request(bare_client: TestClient) -> None:
    response = bare_client.get("/api/sessions/999/workspace")
    assert response.status_code == 401


def test_session_not_found_mapping(api_app: FastAPI) -> None:
    async def _not_found(session_id: int) -> ClinicalContext:
        raise map_workspace_error(WorkspaceSessionNotFound(f"session_id={session_id}"))

    async def _auth(session_id: int) -> AuthorizedWorkspaceSession:
        return _fake_auth(session_id)

    api_app.dependency_overrides[resolve_clinical_context] = _not_found
    api_app.dependency_overrides[resolve_authorized_workspace_read] = _auth
    api_app.dependency_overrides[get_workflow_event_service] = (
        lambda: WorkflowEventService(InMemoryWorkflowEventRepository())
    )
    with TestClient(api_app) as test_client:
        response = test_client.get("/api/sessions/999/workspace")
    api_app.dependency_overrides.clear()
    assert response.status_code == 404
    assert response.json()["detail"] == "WORKSPACE_SESSION_NOT_FOUND"


def test_etag_forwarded_unchanged(client: TestClient) -> None:
    response = client.get(f"/api/sessions/{SESSION_ID}/workspace")
    body = response.json()
    assert response.headers["ETag"] == body["plan_etag"]
    assert len(body["plan_etag"]) == 64  # sha-256 hex from interface mapper


def test_dto_serialization_no_domain_type_names(client: TestClient) -> None:
    response = client.get(f"/api/sessions/{SESSION_ID}/workspace")
    payload = response.text
    for forbidden in (
        "WorkspacePlan",
        "LayoutDirective",
        "ClinicalContext",
        "SpecialtyLens",
        "RoleProfile",
    ):
        assert forbidden not in payload
    WorkspacePlanResponse.model_validate(response.json())


def test_openapi_generation(bare_client: TestClient) -> None:
    response = bare_client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    paths = spec["paths"]
    workspace = paths["/api/sessions/{session_id}/workspace"]["get"]
    trace = paths["/api/sessions/{session_id}/workspace/trace"]["get"]
    assert workspace["summary"] == "Get workspace plan"
    assert "WorkspacePlanResponse" in str(workspace.get("responses", {}))
    assert trace["summary"] == "Get workspace decision trace"
    assert "workspace" in workspace.get("tags", [])


def test_dependency_wiring_use_case_override(client: TestClient, api_app: FastAPI) -> None:
    mock_uc = MagicMock(spec=GenerateWorkspaceUseCase)
    real = GenerateWorkspaceUseCase()
    mock_uc.execute.side_effect = lambda *a, **k: real.execute(*a, **k)
    api_app.dependency_overrides[get_generate_workspace_use_case] = lambda: mock_uc

    response = client.get(f"/api/sessions/{SESSION_ID}/workspace")
    assert response.status_code == 200
    mock_uc.execute.assert_called_once()
    assert mock_uc.execute.call_args.kwargs.get("include_trace") is False


def test_trace_propagation_request_id(client: TestClient) -> None:
    response = client.get(
        f"/api/sessions/{SESSION_ID}/workspace",
        headers={CORRELATION_HEADER: "workspace-corr-test-1"},
    )
    assert response.status_code == 200
    assert response.headers[CORRELATION_HEADER] == "workspace-corr-test-1"


def test_contract_version(client: TestClient) -> None:
    response = client.get(f"/api/sessions/{SESSION_ID}/workspace")
    assert response.json()["contract_version"] == "1.0.0"
    assert response.headers["X-Contract-Version"] == "1.0.0"
    assert CONTRACT_VERSION == "1.0.0"


def test_trace_disabled(client: TestClient, api_app: FastAPI) -> None:
    api_app.dependency_overrides[get_trace_enabled] = lambda: False
    response = client.get(f"/api/sessions/{SESSION_ID}/workspace/trace")
    assert response.status_code == 404
    assert response.json()["detail"] == "WORKSPACE_TRACE_DISABLED"


def test_router_does_not_import_infrastructure() -> None:
    router_path = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "modules"
        / "workspace"
        / "api"
        / "router.py"
    )
    source = router_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden_prefixes = (
        "app.db",
        "app.models",
        "app.services",
        "app.repositories",
        "sqlalchemy",
        "app.infrastructure",
    )
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    for mod in imported:
        for prefix in forbidden_prefixes:
            assert not mod.startswith(prefix), f"router imports infrastructure: {mod}"

    allowed_markers = (
        "fastapi",
        "app.modules.workspace.api",
        "app.modules.workspace.application",
        "app.modules.workspace.interface",
        "app.schemas.clinical_context",
        "app.core.observability.context",
        "typing",
        "__future__",
    )
    for mod in imported:
        assert any(
            mod == m or mod.startswith(m + ".") for m in allowed_markers
        ), f"unexpected import: {mod}"


def test_router_does_not_construct_use_case_inline() -> None:
    source = inspect.getsource(
        __import__("app.modules.workspace.api.router", fromlist=["get_workspace"])
    )
    assert "GenerateWorkspaceUseCase()" not in source
    assert "Depends(get_generate_workspace_use_case)" in source
