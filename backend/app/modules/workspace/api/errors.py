"""API-layer workspace errors — HTTP mapping only; no domain exceptions."""

from __future__ import annotations

from fastapi import HTTPException, status


class WorkspaceSessionNotFound(Exception):
    """Session has no resolvable clinical context (stub / future integration)."""


class WorkspacePermissionDenied(Exception):
    """Caller is not permitted to access this workspace (stub-ready)."""


class WorkspaceValidationError(Exception):
    """Invalid request parameters before compute (lens/role)."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class WorkspaceTraceDisabled(Exception):
    """Trace endpoint disabled via settings stub."""


class WorkspaceComputeFailed(Exception):
    """Unexpected failure while computing a workspace plan."""


class WorkspacePlanStale(Exception):
    """If-Match / ETag mismatch on a mutating endpoint."""


class WorkspaceReadOnly(Exception):
    """Session is locked / closed; mutations are not permitted."""


class WorkspaceObjectNotAcknowledgeable(Exception):
    """Object is not P0 / not acknowledge_required in the current plan."""


class WorkspaceObjectNotResolvable(Exception):
    """Object is not active / not allowed to resolve in the current plan."""


class WorkspaceObjectNotDismissible(Exception):
    """Object is not visible / not allowed to dismiss in the current plan."""


class WorkspaceObjectUnknown(Exception):
    """Unrecognized ClinicalObjectId in a mutation request."""


def map_workspace_error(exc: Exception) -> HTTPException:
    """Map API-layer workspace exceptions to HTTPException with machine-readable codes."""
    if isinstance(exc, WorkspaceSessionNotFound):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="WORKSPACE_SESSION_NOT_FOUND",
        )
    if isinstance(exc, WorkspacePermissionDenied):
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="WORKSPACE_ACCESS_DENIED",
        )
    if isinstance(exc, WorkspaceValidationError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.code,
        )
    if isinstance(exc, WorkspaceObjectUnknown):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="WORKSPACE_OBJECT_UNKNOWN",
        )
    if isinstance(exc, WorkspaceTraceDisabled):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="WORKSPACE_TRACE_DISABLED",
        )
    if isinstance(exc, WorkspacePlanStale):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="WORKSPACE_PLAN_STALE",
        )
    if isinstance(exc, WorkspaceReadOnly):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="WORKSPACE_READ_ONLY",
        )
    if isinstance(exc, WorkspaceObjectNotAcknowledgeable):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="WORKSPACE_OBJECT_NOT_ACKNOWLEDGEABLE",
        )
    if isinstance(exc, WorkspaceObjectNotResolvable):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="WORKSPACE_OBJECT_NOT_RESOLVABLE",
        )
    if isinstance(exc, WorkspaceObjectNotDismissible):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="WORKSPACE_OBJECT_NOT_DISMISSIBLE",
        )
    if isinstance(exc, WorkspaceComputeFailed):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="WORKSPACE_COMPUTE_FAILED",
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="WORKSPACE_COMPUTE_FAILED",
    )
