"""Workspace FastAPI adapter — validate, DI, use case, map DTO; no business logic."""

from __future__ import annotations

from typing import NoReturn

from fastapi import APIRouter, Depends, Query, Response

from app.core.observability.context import bind
from app.modules.workspace.api.dependencies import (
    AuthorizedWorkspaceSession,
    ClinicalContentInputs,
    best_effort_record_audit,
    get_generate_workspace_use_case,
    get_trace_enabled,
    get_workflow_event_service,
    parse_lens,
    parse_object_id,
    parse_role,
    require_if_match,
    resolve_authorized_workspace_mutate,
    resolve_authorized_workspace_read,
    resolve_clinical_content_inputs,
    resolve_clinical_context,
    resolve_session_locked,
)
from app.modules.workspace.api.errors import (
    WorkspaceComputeFailed,
    WorkspaceObjectNotAcknowledgeable,
    WorkspaceObjectNotDismissible,
    WorkspaceObjectNotResolvable,
    WorkspaceObjectUnknown,
    WorkspacePermissionDenied,
    WorkspacePlanStale,
    WorkspaceReadOnly,
    WorkspaceSessionNotFound,
    WorkspaceTraceDisabled,
    WorkspaceValidationError,
    map_workspace_error,
)
from app.modules.workspace.api.responses import apply_workspace_headers
from app.modules.workspace.application.context_hash import compute_context_hash
from app.modules.workspace.application.generate_workspace import GenerateWorkspaceUseCase
from app.modules.workspace.application.inputs import ReviewAcknowledgements, SessionState
from app.modules.workspace.application.workflow.eligibility import (
    is_acknowledgeable,
    is_dismissible,
    is_resolvable,
)
from app.modules.workspace.application.workflow.events import WorkflowEventType
from app.modules.workspace.application.workflow.service import WorkflowEventService
from app.modules.workspace.interface.clinical_content_dto import ClinicalContentResponse
from app.modules.workspace.interface.clinical_content_mappers import (
    to_clinical_content_response,
)
from app.modules.workspace.interface.dto import (
    AcknowledgementRequest,
    DecisionTraceResponse,
    StoryStatusResponse,
    WorkspacePlanResponse,
)
from app.modules.workspace.interface.mappers import (
    to_decision_trace_response,
    to_workspace_plan_response,
)
from app.schemas.clinical_context import ClinicalContext

router = APIRouter(prefix="/api/sessions", tags=["workspace"])

_MAPPED_ERRORS = (
    WorkspaceSessionNotFound,
    WorkspacePermissionDenied,
    WorkspaceValidationError,
    WorkspaceTraceDisabled,
    WorkspaceComputeFailed,
    WorkspacePlanStale,
    WorkspaceReadOnly,
    WorkspaceObjectNotAcknowledgeable,
    WorkspaceObjectNotResolvable,
    WorkspaceObjectNotDismissible,
    WorkspaceObjectUnknown,
)


def _reraise_as_http(exc: Exception) -> NoReturn:
    if isinstance(exc, _MAPPED_ERRORS):
        raise map_workspace_error(exc) from exc
    raise map_workspace_error(WorkspaceComputeFailed(str(exc))) from exc


def _session_state_for(
    auth: AuthorizedWorkspaceSession,
    *,
    offline: bool = False,
    session_closed: bool = False,
) -> SessionState:
    locked = resolve_session_locked(auth.session) or session_closed
    soap_status_raw = getattr(auth.session, "soap_status", None)
    soap_status = (
        soap_status_raw.value
        if soap_status_raw is not None and hasattr(soap_status_raw, "value")
        else (str(soap_status_raw) if soap_status_raw else "pending")
    )
    if soap_status not in {"pending", "generating", "failed", "ready"}:
        soap_status = "pending"
    return SessionState(
        soap_status=soap_status,  # type: ignore[arg-type]
        offline=offline,
        session_locked=locked,
        soap_exists=soap_status in {"ready", "generating", "failed"},
    )


async def _compute_plan_response(
    *,
    context: ClinicalContext,
    auth: AuthorizedWorkspaceSession,
    workflow: WorkflowEventService,
    use_case: GenerateWorkspaceUseCase,
    lens: str,
    role: str,
    offline: bool = False,
    include_trace: bool = False,
):
    specialty_lens = parse_lens(lens)
    role_profile = parse_role(role)
    context_hash = compute_context_hash(context)
    folded = await workflow.get_folded_state(auth.session.id, context_hash)
    session_state = _session_state_for(
        auth, offline=offline, session_closed=folded.session_closed
    )
    plan = use_case.execute(
        context,
        lens=specialty_lens,
        role=role_profile,
        session_state=session_state,
        review_state=folded.review_state,
        include_trace=include_trace,
    )
    dto = to_workspace_plan_response(
        plan, acknowledgement_state_version=folded.version
    )
    return plan, dto, folded.review_state, folded.version


async def _best_effort_audit(
    auth: AuthorizedWorkspaceSession,
    *,
    action: str,
    resource_id: int,
) -> None:
    await best_effort_record_audit(auth, action=action, resource_id=resource_id)


def _assert_mutations_allowed(
    auth: AuthorizedWorkspaceSession, session_closed: bool
) -> None:
    if resolve_session_locked(auth.session) or session_closed:
        raise WorkspaceReadOnly()


def _assert_etag_match(if_match: str, plan_etag: str) -> None:
    if if_match != plan_etag:
        raise WorkspacePlanStale()


@router.get(
    "/{session_id}/workspace",
    response_model=WorkspacePlanResponse,
    summary="Get workspace plan",
    description=(
        "Compute and return the current WorkspacePlan for a session. "
        "Uses GenerateWorkspaceUseCase and interface mappers; does not serialize "
        "ClinicalContext or domain models directly."
    ),
    responses={
        200: {"description": "Workspace plan computed successfully"},
        404: {"description": "WORKSPACE_SESSION_NOT_FOUND"},
        403: {"description": "WORKSPACE_ACCESS_DENIED"},
        422: {"description": "WORKSPACE_LENS_UNKNOWN or WORKSPACE_ROLE_UNKNOWN"},
        500: {"description": "WORKSPACE_COMPUTE_FAILED"},
    },
    tags=["workspace"],
)
async def get_workspace(
    session_id: int,
    response: Response,
    lens: str = Query(default="general_medicine"),
    role: str = Query(default="doctor"),
    offline: bool = Query(default=False),
    auth: AuthorizedWorkspaceSession = Depends(resolve_authorized_workspace_read),
    context: ClinicalContext = Depends(resolve_clinical_context),
    use_case: GenerateWorkspaceUseCase = Depends(get_generate_workspace_use_case),
    workflow: WorkflowEventService = Depends(get_workflow_event_service),
) -> WorkspacePlanResponse:
    bind(session_id=session_id, module="workspace")
    try:
        # Record open BEFORE compute so plan_etag includes the event version.
        context_hash = compute_context_hash(context)
        opened = await workflow.record_workspace_opened_once(
            session_id=session_id,
            actor_user_id=auth.user.id,
            context_hash=context_hash,
        )
        if opened:
            await _best_effort_audit(
                auth, action="view_workspace", resource_id=session_id
            )
        _, dto, _, _ = await _compute_plan_response(
            context=context,
            auth=auth,
            workflow=workflow,
            use_case=use_case,
            lens=lens,
            role=role,
            offline=offline,
            include_trace=False,
        )
    except Exception as exc:
        _reraise_as_http(exc)

    apply_workspace_headers(response, plan_etag=dto.plan_etag)
    return dto


@router.get(
    "/{session_id}/workspace/trace",
    response_model=DecisionTraceResponse,
    summary="Get workspace decision trace",
    description=(
        "Return DecisionTrace for debugging. Projects the same GenerateWorkspaceUseCase "
        "result through to_decision_trace_response. Not physician-facing by default."
    ),
    responses={
        200: {"description": "Decision trace computed successfully"},
        404: {
            "description": "WORKSPACE_SESSION_NOT_FOUND or WORKSPACE_TRACE_DISABLED"
        },
        403: {"description": "WORKSPACE_ACCESS_DENIED"},
        422: {"description": "WORKSPACE_LENS_UNKNOWN or WORKSPACE_ROLE_UNKNOWN"},
        500: {"description": "WORKSPACE_COMPUTE_FAILED"},
    },
    tags=["workspace"],
)
async def get_workspace_trace(
    session_id: int,
    response: Response,
    lens: str = Query(default="general_medicine"),
    role: str = Query(default="doctor"),
    offline: bool = Query(default=False),
    auth: AuthorizedWorkspaceSession = Depends(resolve_authorized_workspace_read),
    context: ClinicalContext = Depends(resolve_clinical_context),
    use_case: GenerateWorkspaceUseCase = Depends(get_generate_workspace_use_case),
    workflow: WorkflowEventService = Depends(get_workflow_event_service),
    trace_enabled: bool = Depends(get_trace_enabled),
) -> DecisionTraceResponse:
    bind(session_id=session_id, module="workspace")
    try:
        if not trace_enabled:
            raise WorkspaceTraceDisabled()
        plan, plan_dto, _, _ = await _compute_plan_response(
            context=context,
            auth=auth,
            workflow=workflow,
            use_case=use_case,
            lens=lens,
            role=role,
            offline=offline,
            include_trace=True,
        )
        trace_dto = to_decision_trace_response(plan, plan_dto.plan_etag)
    except Exception as exc:
        _reraise_as_http(exc)

    apply_workspace_headers(response, plan_etag=plan_dto.plan_etag)
    return trace_dto


@router.get(
    "/{session_id}/clinical-content",
    response_model=ClinicalContentResponse,
    summary="Get clinical content projection",
    description=(
        "Project ClinicalContext into a versioned ClinicalContentResponse envelope "
        "for Doctor Workspace card bodies. Does not serialize ClinicalContext or "
        "alter WorkspacePlan contracts."
    ),
    responses={
        200: {"description": "Clinical content projected successfully"},
        404: {"description": "WORKSPACE_SESSION_NOT_FOUND"},
        403: {"description": "WORKSPACE_ACCESS_DENIED"},
        500: {"description": "WORKSPACE_COMPUTE_FAILED"},
    },
    tags=["workspace"],
)
async def get_clinical_content(
    session_id: int,
    inputs: ClinicalContentInputs = Depends(resolve_clinical_content_inputs),
) -> ClinicalContentResponse:
    bind(session_id=session_id, module="workspace")
    try:
        return to_clinical_content_response(inputs.context, inputs.adapters)
    except Exception as exc:
        _reraise_as_http(exc)


@router.post(
    "/{session_id}/workspace/acknowledgements",
    response_model=WorkspacePlanResponse,
    summary="Acknowledge P0 queue object",
    responses={
        200: {"description": "Acknowledgement recorded; recomputed plan"},
        403: {"description": "WORKSPACE_ACCESS_DENIED"},
        409: {
            "description": (
                "WORKSPACE_PLAN_STALE | WORKSPACE_OBJECT_NOT_ACKNOWLEDGEABLE | "
                "WORKSPACE_READ_ONLY"
            )
        },
        422: {"description": "WORKSPACE_OBJECT_UNKNOWN"},
        500: {"description": "WORKSPACE_COMPUTE_FAILED"},
    },
    tags=["workspace"],
)
async def post_acknowledgement(
    session_id: int,
    body: AcknowledgementRequest,
    response: Response,
    lens: str = Query(default="general_medicine"),
    role: str = Query(default="doctor"),
    if_match: str = Depends(require_if_match),
    auth: AuthorizedWorkspaceSession = Depends(resolve_authorized_workspace_mutate),
    context: ClinicalContext = Depends(resolve_clinical_context),
    use_case: GenerateWorkspaceUseCase = Depends(get_generate_workspace_use_case),
    workflow: WorkflowEventService = Depends(get_workflow_event_service),
) -> WorkspacePlanResponse:
    bind(session_id=session_id, module="workspace")
    try:
        object_id = parse_object_id(body.object_id)
        before_plan, before_dto, review, _ = await _compute_plan_response(
            context=context,
            auth=auth,
            workflow=workflow,
            use_case=use_case,
            lens=lens,
            role=role,
        )
        folded = await workflow.get_folded_state(
            session_id, before_dto.metadata.context_hash
        )
        _assert_mutations_allowed(auth, folded.session_closed)
        _assert_etag_match(if_match, before_dto.plan_etag)

        if not is_acknowledgeable(before_plan, object_id, review):
            raise WorkspaceObjectNotAcknowledgeable()

        context_hash = before_dto.metadata.context_hash
        await workflow.append_if_not_recorded(
            session_id=session_id,
            actor_user_id=auth.user.id,
            event_type=WorkflowEventType.QUEUE_ITEM_VIEWED,
            object_id=object_id.value,
            context_hash=context_hash,
        )
        await workflow.append_if_not_recorded(
            session_id=session_id,
            actor_user_id=auth.user.id,
            event_type=WorkflowEventType.QUEUE_ITEM_ACKNOWLEDGED,
            object_id=object_id.value,
            context_hash=context_hash,
        )
        await _best_effort_audit(
            auth,
            action=workflow.audit_action_for(WorkflowEventType.QUEUE_ITEM_ACKNOWLEDGED),
            resource_id=session_id,
        )
        _, after_dto, _, _ = await _compute_plan_response(
            context=context,
            auth=auth,
            workflow=workflow,
            use_case=use_case,
            lens=lens,
            role=role,
        )
    except Exception as exc:
        _reraise_as_http(exc)

    apply_workspace_headers(response, plan_etag=after_dto.plan_etag)
    return after_dto


@router.post(
    "/{session_id}/workspace/decision-items/{object_id}/resolve",
    response_model=WorkspacePlanResponse,
    summary="Resolve decision queue item",
    responses={
        200: {"description": "Resolve recorded; recomputed plan"},
        403: {"description": "WORKSPACE_ACCESS_DENIED"},
        409: {
            "description": (
                "WORKSPACE_PLAN_STALE | WORKSPACE_OBJECT_NOT_RESOLVABLE | "
                "WORKSPACE_READ_ONLY"
            )
        },
        422: {"description": "WORKSPACE_OBJECT_UNKNOWN"},
        500: {"description": "WORKSPACE_COMPUTE_FAILED"},
    },
    tags=["workspace"],
)
async def post_resolve_decision_item(
    session_id: int,
    object_id: str,
    response: Response,
    lens: str = Query(default="general_medicine"),
    role: str = Query(default="doctor"),
    if_match: str = Depends(require_if_match),
    auth: AuthorizedWorkspaceSession = Depends(resolve_authorized_workspace_mutate),
    context: ClinicalContext = Depends(resolve_clinical_context),
    use_case: GenerateWorkspaceUseCase = Depends(get_generate_workspace_use_case),
    workflow: WorkflowEventService = Depends(get_workflow_event_service),
) -> WorkspacePlanResponse:
    bind(session_id=session_id, module="workspace")
    try:
        oid = parse_object_id(object_id)
        before_plan, before_dto, review, _ = await _compute_plan_response(
            context=context,
            auth=auth,
            workflow=workflow,
            use_case=use_case,
            lens=lens,
            role=role,
        )
        folded = await workflow.get_folded_state(
            session_id, before_dto.metadata.context_hash
        )
        _assert_mutations_allowed(auth, folded.session_closed)
        _assert_etag_match(if_match, before_dto.plan_etag)

        if not is_resolvable(before_plan, oid, review):
            raise WorkspaceObjectNotResolvable()

        context_hash = before_dto.metadata.context_hash
        await workflow.append_if_not_recorded(
            session_id=session_id,
            actor_user_id=auth.user.id,
            event_type=WorkflowEventType.QUEUE_ITEM_VIEWED,
            object_id=oid.value,
            context_hash=context_hash,
        )
        await workflow.append_if_not_recorded(
            session_id=session_id,
            actor_user_id=auth.user.id,
            event_type=WorkflowEventType.QUEUE_ITEM_RESOLVED,
            object_id=oid.value,
            context_hash=context_hash,
        )
        await _best_effort_audit(
            auth,
            action=workflow.audit_action_for(WorkflowEventType.QUEUE_ITEM_RESOLVED),
            resource_id=session_id,
        )
        _, after_dto, _, _ = await _compute_plan_response(
            context=context,
            auth=auth,
            workflow=workflow,
            use_case=use_case,
            lens=lens,
            role=role,
        )
    except Exception as exc:
        _reraise_as_http(exc)

    apply_workspace_headers(response, plan_etag=after_dto.plan_etag)
    return after_dto


@router.post(
    "/{session_id}/workspace/decision-items/{object_id}/dismiss",
    response_model=WorkspacePlanResponse,
    summary="Dismiss decision queue item (visibility only)",
    responses={
        200: {"description": "Dismiss recorded; recomputed plan"},
        403: {"description": "WORKSPACE_ACCESS_DENIED"},
        409: {
            "description": (
                "WORKSPACE_PLAN_STALE | WORKSPACE_OBJECT_NOT_DISMISSIBLE | "
                "WORKSPACE_READ_ONLY"
            )
        },
        422: {"description": "WORKSPACE_OBJECT_UNKNOWN"},
        500: {"description": "WORKSPACE_COMPUTE_FAILED"},
    },
    tags=["workspace"],
)
async def post_dismiss_decision_item(
    session_id: int,
    object_id: str,
    response: Response,
    lens: str = Query(default="general_medicine"),
    role: str = Query(default="doctor"),
    if_match: str = Depends(require_if_match),
    auth: AuthorizedWorkspaceSession = Depends(resolve_authorized_workspace_mutate),
    context: ClinicalContext = Depends(resolve_clinical_context),
    use_case: GenerateWorkspaceUseCase = Depends(get_generate_workspace_use_case),
    workflow: WorkflowEventService = Depends(get_workflow_event_service),
) -> WorkspacePlanResponse:
    bind(session_id=session_id, module="workspace")
    try:
        oid = parse_object_id(object_id)
        before_plan, before_dto, review, _ = await _compute_plan_response(
            context=context,
            auth=auth,
            workflow=workflow,
            use_case=use_case,
            lens=lens,
            role=role,
        )
        folded = await workflow.get_folded_state(
            session_id, before_dto.metadata.context_hash
        )
        _assert_mutations_allowed(auth, folded.session_closed)
        _assert_etag_match(if_match, before_dto.plan_etag)

        if not is_dismissible(before_plan, oid, review):
            raise WorkspaceObjectNotDismissible()

        context_hash = before_dto.metadata.context_hash
        await workflow.append_if_not_recorded(
            session_id=session_id,
            actor_user_id=auth.user.id,
            event_type=WorkflowEventType.QUEUE_ITEM_VIEWED,
            object_id=oid.value,
            context_hash=context_hash,
        )
        await workflow.append_if_not_recorded(
            session_id=session_id,
            actor_user_id=auth.user.id,
            event_type=WorkflowEventType.QUEUE_ITEM_DISMISSED,
            object_id=oid.value,
            context_hash=context_hash,
        )
        await _best_effort_audit(
            auth,
            action=workflow.audit_action_for(WorkflowEventType.QUEUE_ITEM_DISMISSED),
            resource_id=session_id,
        )
        _, after_dto, _, _ = await _compute_plan_response(
            context=context,
            auth=auth,
            workflow=workflow,
            use_case=use_case,
            lens=lens,
            role=role,
        )
    except Exception as exc:
        _reraise_as_http(exc)

    apply_workspace_headers(response, plan_etag=after_dto.plan_etag)
    return after_dto


@router.post(
    "/{session_id}/workspace/story/refresh",
    response_model=WorkspacePlanResponse,
    summary="Physician-requested story regeneration",
    responses={
        200: {"description": "Story refreshed synchronously; recomputed plan"},
        403: {"description": "WORKSPACE_ACCESS_DENIED"},
        409: {"description": "WORKSPACE_PLAN_STALE | WORKSPACE_READ_ONLY"},
        500: {"description": "WORKSPACE_COMPUTE_FAILED"},
    },
    tags=["workspace"],
)
async def post_story_refresh(
    session_id: int,
    response: Response,
    lens: str = Query(default="general_medicine"),
    role: str = Query(default="doctor"),
    if_match: str = Depends(require_if_match),
    auth: AuthorizedWorkspaceSession = Depends(resolve_authorized_workspace_mutate),
    context: ClinicalContext = Depends(resolve_clinical_context),
    use_case: GenerateWorkspaceUseCase = Depends(get_generate_workspace_use_case),
    workflow: WorkflowEventService = Depends(get_workflow_event_service),
) -> WorkspacePlanResponse:
    bind(session_id=session_id, module="workspace")
    try:
        before_plan, before_dto, _, _ = await _compute_plan_response(
            context=context,
            auth=auth,
            workflow=workflow,
            use_case=use_case,
            lens=lens,
            role=role,
        )
        folded = await workflow.get_folded_state(
            session_id, before_dto.metadata.context_hash
        )
        _assert_mutations_allowed(auth, folded.session_closed)
        _assert_etag_match(if_match, before_dto.plan_etag)

        context_hash = before_dto.metadata.context_hash
        await workflow.append_event(
            session_id=session_id,
            actor_user_id=auth.user.id,
            event_type=WorkflowEventType.STORY_REFRESH_REQUESTED,
            context_hash=context_hash,
        )
        await _best_effort_audit(
            auth,
            action=workflow.audit_action_for(WorkflowEventType.STORY_REFRESH_REQUESTED),
            resource_id=session_id,
        )

        after_plan, after_dto, _, _ = await _compute_plan_response(
            context=context,
            auth=auth,
            workflow=workflow,
            use_case=use_case,
            lens=lens,
            role=role,
        )
        if after_plan.story is not None:
            await workflow.append_event(
                session_id=session_id,
                actor_user_id=auth.user.id,
                event_type=WorkflowEventType.STORY_REFRESH_COMPLETED,
                context_hash=context_hash,
            )
            await _best_effort_audit(
                auth,
                action=workflow.audit_action_for(
                    WorkflowEventType.STORY_REFRESH_COMPLETED
                ),
                resource_id=session_id,
            )
        else:
            await workflow.append_event(
                session_id=session_id,
                actor_user_id=auth.user.id,
                event_type=WorkflowEventType.STORY_REFRESH_FAILED,
                context_hash=context_hash,
            )
            await _best_effort_audit(
                auth,
                action=workflow.audit_action_for(
                    WorkflowEventType.STORY_REFRESH_FAILED
                ),
                resource_id=session_id,
            )
        _, after_dto, _, _ = await _compute_plan_response(
            context=context,
            auth=auth,
            workflow=workflow,
            use_case=use_case,
            lens=lens,
            role=role,
        )
    except Exception as exc:
        _reraise_as_http(exc)

    apply_workspace_headers(response, plan_etag=after_dto.plan_etag)
    return after_dto


@router.get(
    "/{session_id}/workspace/story/status",
    response_model=StoryStatusResponse,
    summary="Get clinical story refresh status",
    responses={
        200: {"description": "Story status"},
        403: {"description": "WORKSPACE_ACCESS_DENIED"},
        404: {"description": "WORKSPACE_SESSION_NOT_FOUND"},
        500: {"description": "WORKSPACE_COMPUTE_FAILED"},
    },
    tags=["workspace"],
)
async def get_story_status(
    session_id: int,
    lens: str = Query(default="general_medicine"),
    role: str = Query(default="doctor"),
    auth: AuthorizedWorkspaceSession = Depends(resolve_authorized_workspace_read),
    context: ClinicalContext = Depends(resolve_clinical_context),
    use_case: GenerateWorkspaceUseCase = Depends(get_generate_workspace_use_case),
    workflow: WorkflowEventService = Depends(get_workflow_event_service),
) -> StoryStatusResponse:
    bind(session_id=session_id, module="workspace")
    try:
        plan, dto, review, _ = await _compute_plan_response(
            context=context,
            auth=auth,
            workflow=workflow,
            use_case=use_case,
            lens=lens,
            role=role,
        )
        folded = await workflow.get_folded_state(session_id, dto.metadata.context_hash)
        stale = bool(plan.story.stale) if plan.story is not None else review.story_frozen
        return StoryStatusResponse(
            story_status=folded.story_status,
            context_hash=dto.metadata.context_hash,
            stale=stale,
            plan_etag=dto.plan_etag,
        )
    except Exception as exc:
        _reraise_as_http(exc)
