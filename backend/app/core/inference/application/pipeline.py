"""InferencePipeline — executes requests end-to-end with observability."""

from __future__ import annotations

import time
from datetime import datetime, timezone

from app.core.inference.application.adapter import InferenceAdapter  # noqa: F401 (Protocol ref)
from app.core.inference.application.publisher import (
    InferenceResultPublisher,  # noqa: F401
    NoOpInferenceResultPublisher,
)
from app.core.inference.application.registry import InferenceRegistry
from app.core.inference.domain.models import (
    ExecutionTrace,
    InferenceExecution,
    InferenceRequest,
    InferenceResult,
)
from app.core.observability.stages import PipelineModule, PipelineStage
from app.core.observability.timing import pipeline_stage


class InferencePipeline:
    """Orchestrates the full lifecycle of an inference request.

    Constructor injects a registry and an optional publisher (default NoOp).
    """

    def __init__(
        self,
        registry: InferenceRegistry,
        publisher: InferenceResultPublisher | None = None,
    ) -> None:
        self._registry = registry
        self._publisher: InferenceResultPublisher = (
            publisher if publisher is not None else NoOpInferenceResultPublisher()
        )

    async def execute(self, request: InferenceRequest) -> InferenceResult:
        """Run inference for *request*, publish the result, and return it."""
        execution = InferenceExecution.create(request=request)

        async with pipeline_stage(
            PipelineStage.INFERENCE_EXECUTION,
            module=PipelineModule.INFERENCE,
            session_id=request.session_id,
        ):
            execution = execution.mark_running()
            adapter = self._registry.resolve(request.product_key)

            start = time.perf_counter()
            started_at = datetime.now(timezone.utc)

            async with pipeline_stage(
                PipelineStage.INFERENCE_ADAPTER,
                module=PipelineModule.INFERENCE,
                session_id=request.session_id,
            ):
                raw_result = await adapter.infer(request)

            finished_at = datetime.now(timezone.utc)
            elapsed = time.perf_counter() - start

            # Ensure trace carries product_key and correct timing even if the
            # adapter built its own trace with different values.
            trace = ExecutionTrace(
                started_at=raw_result.execution_trace.started_at
                if raw_result.execution_trace.started_at
                else started_at,
                finished_at=raw_result.execution_trace.finished_at
                if raw_result.execution_trace.finished_at
                else finished_at,
                adapter_name=raw_result.execution_trace.adapter_name,
                adapter_version=raw_result.execution_trace.adapter_version,
                runtime_version=raw_result.execution_trace.runtime_version,
                product_key=request.product_key,  # always stamp from request
            )

            result = InferenceResult(
                execution_id=raw_result.execution_id,
                status=raw_result.status,
                findings=raw_result.findings,
                execution_trace=trace,
                duration=raw_result.duration if raw_result.duration > 0 else elapsed,
                runtime_metadata=raw_result.runtime_metadata,
            )

            execution = execution.complete(result)
            await self._publisher.publish(result)
            return result
