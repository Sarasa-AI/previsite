"""Workspace workflow mutation API tests — ack / resolve / dismiss / story."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.observability.middleware import CorrelationIdMiddleware
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
    get_workflow_event_service,
    resolve_authorized_workspace_mutate,
    resolve_authorized_workspace_read,
    resolve_clinical_context,
)
from app.modules.workspace.application.workflow.in_memory import (
    InMemoryWorkflowEventRepository,
)
from app.modules.workspace.application.workflow.service import WorkflowEventService
from app.modules.workspace.interface.dto import WorkspacePlanResponse
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
    def __init__(self, *, status: str = "active") -> None:
        self.id = SESSION_ID
        self.status = status
        self.soap_status = "ready"


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
        timeline=_timeline("Headache onset", "Nausea", "Photophobia"),
    )


@pytest.fixture
def memory_repo() -> InMemoryWorkflowEventRepository:
    return InMemoryWorkflowEventRepository()


@pytest.fixture
def client(memory_repo: InMemoryWorkflowEventRepository):
    app = FastAPI()
    app.add_middleware(CorrelationIdMiddleware)
    app.include_router(workspace_router)
    fixed = _context()
    workflow = WorkflowEventService(memory_repo)

    async def _override_resolve(session_id: int) -> ClinicalContext:
        return fixed

    async def _override_auth(session_id: int) -> AuthorizedWorkspaceSession:
        return AuthorizedWorkspaceSession(
            session=_FakeSession(), user=_FakeUser(), db=MagicMock()
        )

    app.dependency_overrides[resolve_clinical_context] = _override_resolve
    app.dependency_overrides[resolve_authorized_workspace_read] = _override_auth
    app.dependency_overrides[resolve_authorized_workspace_mutate] = _override_auth
    app.dependency_overrides[get_workflow_event_service] = lambda: workflow
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _etag(client: TestClient) -> str:
    response = client.get(f"/api/sessions/{SESSION_ID}/workspace")
    assert response.status_code == 200
    return response.json()["plan_etag"]


def test_acknowledge_success_and_idempotent(client: TestClient) -> None:
    etag = _etag(client)
    # Find an acknowledge_required object
    plan = client.get(f"/api/sessions/{SESSION_ID}/workspace").json()
    ack_item = next(
        (i for i in plan["decision_queue"] if i["acknowledge_required"]),
        None,
    )
    if ack_item is None:
        # Force via critical labs which is typically P0
        object_id = "critical_labs"
    else:
        object_id = ack_item["object_id"]

    response = client.post(
        f"/api/sessions/{SESSION_ID}/workspace/acknowledgements",
        json={"object_id": object_id},
        headers={"If-Match": etag},
    )
    assert response.status_code == 200, response.text
    dto = WorkspacePlanResponse.model_validate(response.json())
    assert dto.plan_etag != etag

    # Idempotent duplicate
    response2 = client.post(
        f"/api/sessions/{SESSION_ID}/workspace/acknowledgements",
        json={"object_id": object_id},
        headers={"If-Match": dto.plan_etag},
    )
    assert response2.status_code == 200, response2.text


def test_acknowledge_stale_etag(client: TestClient) -> None:
    response = client.post(
        f"/api/sessions/{SESSION_ID}/workspace/acknowledgements",
        json={"object_id": "critical_labs"},
        headers={"If-Match": "not-the-real-etag"},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "WORKSPACE_PLAN_STALE"


def test_acknowledge_unknown_object(client: TestClient) -> None:
    etag = _etag(client)
    response = client.post(
        f"/api/sessions/{SESSION_ID}/workspace/acknowledgements",
        json={"object_id": "not_a_real_object"},
        headers={"If-Match": etag},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "WORKSPACE_OBJECT_UNKNOWN"


def test_resolve_and_dismiss(client: TestClient) -> None:
    etag = _etag(client)
    plan = client.get(f"/api/sessions/{SESSION_ID}/workspace").json()
    queue_ids = [i["object_id"] for i in plan["decision_queue"]]
    object_id = queue_ids[0] if queue_ids else "medications"

    resolve = client.post(
        f"/api/sessions/{SESSION_ID}/workspace/decision-items/{object_id}/resolve",
        json={},
        headers={"If-Match": etag},
    )
    assert resolve.status_code == 200, resolve.text
    resolved_plan = resolve.json()
    assert object_id not in [i["object_id"] for i in resolved_plan["decision_queue"]]

    # Dismiss another visible object
    etag2 = resolved_plan["plan_etag"]
    dismiss_id = next(
        (
            d["object_id"]
            for d in resolved_plan["layout_directives"]
            if d["slot"] != "hidden"
            and d["object_id"]
            not in {"chief_complaint", "allergies", "snapshot", object_id}
        ),
        None,
    )
    if dismiss_id:
        dismiss = client.post(
            f"/api/sessions/{SESSION_ID}/workspace/decision-items/{dismiss_id}/dismiss",
            json={},
            headers={"If-Match": etag2},
        )
        assert dismiss.status_code == 200, dismiss.text
        dismissed = next(
            d
            for d in dismiss.json()["layout_directives"]
            if d["object_id"] == dismiss_id
        )
        assert dismissed["slot"] == "hidden"
        assert dismissed["visibility_reason"] == "physician_dismissed"


def test_resolve_idempotent(client: TestClient) -> None:
    etag = _etag(client)
    object_id = "medications"
    r1 = client.post(
        f"/api/sessions/{SESSION_ID}/workspace/decision-items/{object_id}/resolve",
        headers={"If-Match": etag},
    )
    assert r1.status_code == 200
    r2 = client.post(
        f"/api/sessions/{SESSION_ID}/workspace/decision-items/{object_id}/resolve",
        headers={"If-Match": r1.json()["plan_etag"]},
    )
    assert r2.status_code == 200


def test_read_only_rejects_mutations(memory_repo: InMemoryWorkflowEventRepository) -> None:
    app = FastAPI()
    app.add_middleware(CorrelationIdMiddleware)
    app.include_router(workspace_router)
    fixed = _context()
    workflow = WorkflowEventService(memory_repo)

    async def _override_resolve(session_id: int) -> ClinicalContext:
        return fixed

    async def _override_auth(session_id: int) -> AuthorizedWorkspaceSession:
        return AuthorizedWorkspaceSession(
            session=_FakeSession(status="completed"),
            user=_FakeUser(),
            db=MagicMock(),
        )

    app.dependency_overrides[resolve_clinical_context] = _override_resolve
    app.dependency_overrides[resolve_authorized_workspace_read] = _override_auth
    app.dependency_overrides[resolve_authorized_workspace_mutate] = _override_auth
    app.dependency_overrides[get_workflow_event_service] = lambda: workflow
    with TestClient(app) as client:
        etag = client.get(f"/api/sessions/{SESSION_ID}/workspace").json()["plan_etag"]
        response = client.post(
            f"/api/sessions/{SESSION_ID}/workspace/acknowledgements",
            json={"object_id": "critical_labs"},
            headers={"If-Match": etag},
        )
        assert response.status_code == 409
        assert response.json()["detail"] == "WORKSPACE_READ_ONLY"
    app.dependency_overrides.clear()


def test_story_refresh_and_status(client: TestClient) -> None:
    etag = _etag(client)
    refresh = client.post(
        f"/api/sessions/{SESSION_ID}/workspace/story/refresh",
        json={},
        headers={"If-Match": etag},
    )
    assert refresh.status_code == 200, refresh.text
    WorkspacePlanResponse.model_validate(refresh.json())

    status = client.get(f"/api/sessions/{SESSION_ID}/workspace/story/status")
    assert status.status_code == 200
    body = status.json()
    assert body["story_status"] in {
        "ready",
        "refresh_requested",
        "generating",
        "failed",
    }
    assert "context_hash" in body
    assert "stale" in body
    assert "plan_etag" in body
