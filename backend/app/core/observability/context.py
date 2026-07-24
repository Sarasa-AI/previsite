"""Request/pipeline correlation context via contextvars."""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)
_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_session_id: ContextVar[int | None] = ContextVar("session_id", default=None)
_patient_id: ContextVar[int | None] = ContextVar("patient_id", default=None)
_pipeline_stage: ContextVar[str | None] = ContextVar("pipeline_stage", default=None)
_module: ContextVar[str | None] = ContextVar("module", default=None)


@dataclass(frozen=True)
class ObservabilityContext:
    correlation_id: str | None = None
    request_id: str | None = None
    session_id: int | None = None
    patient_id: int | None = None
    pipeline_stage: str | None = None
    module: str | None = None

    def as_log_extra(self) -> dict[str, Any]:
        extra: dict[str, Any] = {}
        if self.correlation_id:
            extra["correlation_id"] = self.correlation_id
            extra["request_id"] = self.request_id or self.correlation_id
        if self.session_id is not None:
            extra["session_id"] = self.session_id
        if self.patient_id is not None:
            extra["patient_id"] = self.patient_id
        if self.pipeline_stage:
            extra["pipeline_stage"] = self.pipeline_stage
        if self.module:
            extra["module"] = self.module
        return extra


def new_correlation_id() -> str:
    return str(uuid.uuid4())


def get_correlation_id() -> str | None:
    return _correlation_id.get()


def get_context() -> ObservabilityContext:
    return ObservabilityContext(
        correlation_id=_correlation_id.get(),
        request_id=_request_id.get() or _correlation_id.get(),
        session_id=_session_id.get(),
        patient_id=_patient_id.get(),
        pipeline_stage=_pipeline_stage.get(),
        module=_module.get(),
    )


def bind(
    *,
    correlation_id: str | None = None,
    request_id: str | None = None,
    session_id: int | None = None,
    patient_id: int | None = None,
    pipeline_stage: str | None = None,
    module: str | None = None,
) -> None:
    """Bind fields onto the current context. None values leave existing bindings unchanged."""
    if correlation_id is not None:
        _correlation_id.set(correlation_id)
        if request_id is None:
            _request_id.set(correlation_id)
    if request_id is not None:
        _request_id.set(request_id)
    if session_id is not None:
        _session_id.set(session_id)
    if patient_id is not None:
        _patient_id.set(patient_id)
    if pipeline_stage is not None:
        _pipeline_stage.set(pipeline_stage)
    if module is not None:
        _module.set(module)


def clear() -> None:
    _correlation_id.set(None)
    _request_id.set(None)
    _session_id.set(None)
    _patient_id.set(None)
    _pipeline_stage.set(None)
    _module.set(None)
