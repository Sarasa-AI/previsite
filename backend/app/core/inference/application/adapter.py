"""InferenceAdapter Protocol — structural type for all product adapters."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.core.inference.domain.models import InferenceRequest, InferenceResult


@runtime_checkable
class InferenceAdapter(Protocol):
    """Structural protocol every product adapter must satisfy."""

    @property
    def name(self) -> str:
        """Stable adapter identifier (e.g. 'retina-v1', 'fake')."""
        ...

    @property
    def version(self) -> str:
        """Adapter implementation version string."""
        ...

    async def infer(self, request: InferenceRequest) -> InferenceResult:
        """Run inference for the given request and return a result."""
        ...
