"""Production observability kit for the Clinical AI pipeline.

Reusable by every current and future clinical module without redesign.
"""

from app.core.observability.context import (
    bind,
    clear,
    get_context,
    get_correlation_id,
    new_correlation_id,
)
from app.core.observability.errors import emit_pipeline_failure
from app.core.observability.metrics import metrics_response
from app.core.observability.stages import PipelineModule, PipelineStage
from app.core.observability.telemetry import (
    AITelemetryEvent,
    ClinicalPipelineEvent,
    build_ai_telemetry_event,
    build_pipeline_event,
    emit_ai_telemetry,
    emit_pipeline_event,
)
from app.core.observability.timing import pipeline_stage, pipeline_stage_sync

__all__ = [
    "AITelemetryEvent",
    "ClinicalPipelineEvent",
    "PipelineModule",
    "PipelineStage",
    "bind",
    "build_ai_telemetry_event",
    "build_pipeline_event",
    "clear",
    "emit_ai_telemetry",
    "emit_pipeline_event",
    "emit_pipeline_failure",
    "get_context",
    "get_correlation_id",
    "metrics_response",
    "new_correlation_id",
    "pipeline_stage",
    "pipeline_stage_sync",
]
