"""Dependency providers for Workspace API — auth, session access, ClinicalContextBuilder."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.session_access import get_authorized_session, is_patient
from app.db.database import get_db
from app.models import User
from app.models import Session as DBSession
from app.models.session import SessionStatus
from app.modules.workspace.api.errors import (
    WorkspaceObjectUnknown,
    WorkspacePermissionDenied,
    WorkspacePlanStale,
    WorkspaceSessionNotFound,
    WorkspaceValidationError,
    map_workspace_error,
)
from app.modules.workspace.application.generate_workspace import (
    GenerateWorkspaceUseCase,
    generate_workspace,
)
from app.modules.workspace.application.inputs import OrchestratorInputs
from app.modules.workspace.application.projections.adapters import ClinicalContentAdapters
from app.modules.workspace.application.workflow.service import WorkflowEventService
from app.modules.workspace.domain.enums import ClinicalObjectId, RoleProfile, SpecialtyLens
from app.modules.workspace.infrastructure.models import (  # noqa: F401 — register Base metadata
    WorkflowEventRecord,
)
from app.modules.workspace.infrastructure.workflow_repository import (
    SqlAlchemyWorkflowEventRepository,
)
from app.modules.workspace.interface.clinical_content_mappers import (
    load_clinical_content_adapters,
)
from app.modules.workspace.interface.orchestrator_inputs import (
    context_only_orchestrator_inputs,
    load_orchestrator_inputs,
)
from app.schemas.clinical_context import ClinicalContext
from app.services.clinical_context_builder import clinical_context_builder


@dataclass(frozen=True)
class ClinicalContentInputs:
    """Authorized ClinicalContext + allowed non-clinical adapters."""

    context: ClinicalContext
    adapters: ClinicalContentAdapters


@dataclass(frozen=True)
class AuthorizedWorkspaceSession:
    """Authorized DB session + current user for workspace mutations / reads."""

    session: DBSession
    user: User
    db: AsyncSession


def get_generate_workspace_use_case() -> GenerateWorkspaceUseCase:
    return generate_workspace


def get_trace_enabled() -> bool:
    """Trace endpoint enabled. Override in tests / settings when configured."""
    return True


def get_workflow_event_service(
    db: AsyncSession = Depends(get_db),
) -> WorkflowEventService:
    """Workflow Event Store service. Override in tests with an in-memory fake."""
    return WorkflowEventService(SqlAlchemyWorkflowEventRepository(db))


def parse_lens(lens: str) -> SpecialtyLens:
    try:
        return SpecialtyLens(lens)
    except ValueError as exc:
        raise WorkspaceValidationError("WORKSPACE_LENS_UNKNOWN") from exc


def parse_role(role: str) -> RoleProfile:
    try:
        return RoleProfile(role)
    except ValueError as exc:
        raise WorkspaceValidationError("WORKSPACE_ROLE_UNKNOWN") from exc


def parse_object_id(object_id: str) -> ClinicalObjectId:
    try:
        return ClinicalObjectId(object_id)
    except ValueError as exc:
        raise WorkspaceObjectUnknown(object_id) from exc


def resolve_session_locked(session: DBSession) -> bool:
    """True when mutations must be rejected (read-only / closed).

    Uses existing SessionStatus.COMPLETED as the lock signal for this sprint;
    full SessionClosed workflow is deferred.
    """
    status = session.status
    value = status.value if hasattr(status, "value") else str(status)
    return value == SessionStatus.COMPLETED.value


def _map_session_http_error(exc: HTTPException) -> HTTPException:
    """Translate session_access HTTPException into workspace machine-readable codes."""
    if exc.status_code == 403:
        return map_workspace_error(WorkspacePermissionDenied())
    if exc.status_code == 404:
        return map_workspace_error(WorkspaceSessionNotFound())
    return exc


async def _authorize_workspace_session(
    db: AsyncSession,
    session_id: int,
    current_user: User,
    *,
    claim: bool = False,
) -> DBSession:
    if is_patient(current_user):
        raise map_workspace_error(WorkspacePermissionDenied())

    try:
        return await get_authorized_session(
            db, session_id, current_user, claim=claim
        )
    except HTTPException as exc:
        raise _map_session_http_error(exc) from exc


async def resolve_clinical_context(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ClinicalContext:
    """Authorize session access and build ClinicalContext for workspace compute."""
    await _authorize_workspace_session(db, session_id, current_user, claim=False)

    try:
        return await clinical_context_builder.build(db, session_id)
    except ValueError as exc:
        raise map_workspace_error(WorkspaceSessionNotFound(str(exc))) from exc


async def resolve_orchestrator_inputs(
    session_id: int,
    context: ClinicalContext = Depends(resolve_clinical_context),
    db: AsyncSession = Depends(get_db),
) -> OrchestratorInputs:
    """Build the adapter-signal bundle the orchestrator consumes.

    Without this the router computed every plan from ``OrchestratorInputs()``
    defaults, which permanently hid RED_FLAGS / CONFLICTS / DOCUMENTS regardless of
    the session's real data. Override in tests to inject deterministic signals.
    """
    if db is None:  # pragma: no cover — defensive; FastAPI always supplies a session
        return context_only_orchestrator_inputs(context)
    return await load_orchestrator_inputs(db, session_id, context)


async def resolve_authorized_workspace_read(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AuthorizedWorkspaceSession:
    """Authorize without claim — for GET workspace / story status."""
    session = await _authorize_workspace_session(
        db, session_id, current_user, claim=False
    )
    return AuthorizedWorkspaceSession(session=session, user=current_user, db=db)


async def resolve_authorized_workspace_mutate(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AuthorizedWorkspaceSession:
    """Authorize with claim=True — for POST acknowledgements / resolve / dismiss / refresh."""
    session = await _authorize_workspace_session(
        db, session_id, current_user, claim=True
    )
    return AuthorizedWorkspaceSession(session=session, user=current_user, db=db)


def require_if_match(
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> str:
    """Require If-Match header on mutating endpoints."""
    if not if_match or not if_match.strip():
        raise map_workspace_error(WorkspacePlanStale())
    # Strip weak validators / quotes if present.
    value = if_match.strip()
    if value.startswith("W/"):
        value = value[2:].strip()
    if value.startswith('"') and value.endswith('"'):
        value = value[1:-1]
    return value


async def resolve_clinical_content_inputs(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ClinicalContentInputs:
    """Authorize, build ClinicalContext, and load allowed content adapters."""
    session = await _authorize_workspace_session(
        db, session_id, current_user, claim=False
    )

    try:
        context = await clinical_context_builder.build(db, session_id)
    except ValueError as exc:
        raise map_workspace_error(WorkspaceSessionNotFound(str(exc))) from exc

    adapters = await load_clinical_content_adapters(db, session)
    return ClinicalContentInputs(context=context, adapters=adapters)


async def best_effort_record_audit(
    auth: AuthorizedWorkspaceSession,
    *,
    action: str,
    resource_id: int,
) -> None:
    """Fail-soft AuditLog mirror — never rolls back a committed workflow event."""
    from app.services.audit_service import record_audit

    await record_audit(
        auth.db,
        action=action,
        user_id=auth.user.id,
        resource_type="workspace",
        resource_id=resource_id,
    )
