"""Workflow Event Store repository + service integration tests (real DB)."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.workspace.application.workflow.events import WorkflowEventType
from app.modules.workspace.application.workflow.service import WorkflowEventService
from app.modules.workspace.infrastructure.workflow_repository import (
    SqlAlchemyWorkflowEventRepository,
)
from app.models import Session as SessionModel
from app.models.user import User, UserRole
from app.auth.security import get_password_hash


async def _seed_session(db: AsyncSession) -> tuple[int, int]:
    user = User(
        email="wf-repo@test.com",
        full_name="wf_repo",
        hashed_password=get_password_hash("VeryStrongPassword123!"),
        role=UserRole.DOCTOR,
        is_active=True,
    )
    patient = User(
        email="wf-patient@test.com",
        full_name="wf_patient",
        hashed_password=get_password_hash("VeryStrongPassword123!"),
        role=UserRole.PATIENT,
        is_active=True,
    )
    db.add(patient)
    db.add(user)
    await db.flush()
    session = SessionModel(patient_id=patient.id, doctor_id=user.id)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    await db.refresh(user)
    return session.id, user.id


@pytest.mark.asyncio
async def test_append_and_list_ordering(db: AsyncSession) -> None:
    session_id, user_id = await _seed_session(db)
    repo = SqlAlchemyWorkflowEventRepository(db)
    service = WorkflowEventService(repo)

    await service.append_event(
        session_id=session_id,
        actor_user_id=user_id,
        event_type=WorkflowEventType.WORKSPACE_OPENED,
        context_hash="h1",
    )
    await service.append_event(
        session_id=session_id,
        actor_user_id=user_id,
        event_type=WorkflowEventType.QUEUE_ITEM_ACKNOWLEDGED,
        object_id="conflicts",
        context_hash="h1",
    )
    events = await service.list_events(session_id)
    assert len(events) == 2
    assert events[0].event_type is WorkflowEventType.WORKSPACE_OPENED
    assert events[1].event_type is WorkflowEventType.QUEUE_ITEM_ACKNOWLEDGED
    assert events[0].id < events[1].id


@pytest.mark.asyncio
async def test_fold_from_persisted_events(db: AsyncSession) -> None:
    session_id, user_id = await _seed_session(db)
    service = WorkflowEventService(SqlAlchemyWorkflowEventRepository(db))
    await service.append_event(
        session_id=session_id,
        actor_user_id=user_id,
        event_type=WorkflowEventType.QUEUE_ITEM_DISMISSED,
        object_id="labs",
        context_hash="ctx",
    )
    folded = await service.get_folded_state(session_id, "ctx")
    assert any(o.value == "labs" for o in folded.review_state.dismissed_objects)
    assert folded.version == "1"


@pytest.mark.asyncio
async def test_append_if_not_recorded_idempotent(db: AsyncSession) -> None:
    session_id, user_id = await _seed_session(db)
    service = WorkflowEventService(SqlAlchemyWorkflowEventRepository(db))
    e1, dup1 = await service.append_if_not_recorded(
        session_id=session_id,
        actor_user_id=user_id,
        event_type=WorkflowEventType.QUEUE_ITEM_RESOLVED,
        object_id="medications",
        context_hash="ctx",
    )
    e2, dup2 = await service.append_if_not_recorded(
        session_id=session_id,
        actor_user_id=user_id,
        event_type=WorkflowEventType.QUEUE_ITEM_RESOLVED,
        object_id="medications",
        context_hash="ctx",
    )
    assert dup1 is False and e1 is not None
    assert dup2 is True and e2 is None
    events = await service.list_events(session_id)
    assert len(events) == 1


@pytest.mark.asyncio
async def test_workspace_opened_once_per_day(db: AsyncSession) -> None:
    session_id, user_id = await _seed_session(db)
    service = WorkflowEventService(SqlAlchemyWorkflowEventRepository(db))
    first = await service.record_workspace_opened_once(
        session_id=session_id, actor_user_id=user_id, context_hash="ctx"
    )
    second = await service.record_workspace_opened_once(
        session_id=session_id, actor_user_id=user_id, context_hash="ctx"
    )
    assert first is True
    assert second is False
    events = await service.list_events(session_id)
    assert len(events) == 1
