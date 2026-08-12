"""Inference Runtime Foundation — public API surface."""

from __future__ import annotations

from app.core.inference.application.adapter import InferenceAdapter
from app.core.inference.application.fake_adapter import FakeInferenceAdapter
from app.core.inference.application.pipeline import InferencePipeline
from app.core.inference.application.publisher import (
    InferenceResultPublisher,
    NoOpInferenceResultPublisher,
)
from app.core.inference.application.registry import InferenceRegistry
from app.core.inference.domain.enums import InferenceStatus
from app.core.inference.domain.models import (
    INFERENCE_SCHEMA_VERSION,
    ExecutionTrace,
    InferenceExecution,
    InferenceFinding,
    InferenceRequest,
    InferenceResult,
)
from app.core.inference.infrastructure import RUNTIME_VERSION

__all__ = [
    # domain
    "InferenceStatus",
    "InferenceRequest",
    "InferenceFinding",
    "ExecutionTrace",
    "InferenceResult",
    "InferenceExecution",
    "INFERENCE_SCHEMA_VERSION",
    # application
    "InferenceAdapter",
    "InferenceResultPublisher",
    "NoOpInferenceResultPublisher",
    "InferenceRegistry",
    "InferencePipeline",
    "FakeInferenceAdapter",
    # infrastructure
    "RUNTIME_VERSION",
]
