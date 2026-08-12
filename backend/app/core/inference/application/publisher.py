"""InferenceResultPublisher Protocol + NoOp implementation."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.core.inference.domain.models import InferenceResult


@runtime_checkable
class InferenceResultPublisher(Protocol):
    """Composition port for downstream result consumers (events, telemetry, persistence)."""

    async def publish(self, result: InferenceResult) -> None:
        """Publish a completed inference result to downstream consumers."""
        ...


class NoOpInferenceResultPublisher:
    """Default publisher — discards the result with no side effects."""

    async def publish(self, result: InferenceResult) -> None:
        return None
