"""OpenRouter inference adapter — implements InferenceAdapter protocol."""

from __future__ import annotations

import time
from datetime import datetime, timezone

from app.core.inference.application.adapter import InferenceAdapter
from app.core.inference.domain.enums import InferenceStatus
from app.core.inference.domain.models import (
    ExecutionTrace,
    InferenceRequest,
    InferenceResult,
)
from app.core.inference.infrastructure import RUNTIME_VERSION
from app.core.inference.infrastructure.providers.openrouter.client import (
    OpenRouterClient,
)
from app.core.inference.infrastructure.providers.openrouter.mapper import (
    map_structured_output_to_findings,
)
from app.core.inference.infrastructure.providers.openrouter.prompts import (
    build_inference_messages,
)


class OpenRouterInferenceAdapter:
    """OpenRouter-backed inference adapter.

    This adapter implements the InferenceAdapter protocol and provides
    structured inference through the OpenRouter API.

    Parameters
    ----------
    client : OpenRouterClient
        Configured OpenRouter HTTP client.

    Notes
    -----
    Provider exceptions propagate to the caller according to the existing
    InferencePipeline contract. This adapter does not swallow or transform
    provider errors into FAILED status results.

    The adapter treats context_reference as opaque. Clinical context resolution
    is outside the scope of this provider layer.
    """

    def __init__(self, client: OpenRouterClient) -> None:
        self._client = client

    @property
    def name(self) -> str:
        """Adapter identifier."""
        return "openrouter"

    @property
    def version(self) -> str:
        """Adapter implementation version."""
        return "1.0.0"

    async def infer(self, request: InferenceRequest) -> InferenceResult:
        """Execute inference for the given request.

        Parameters
        ----------
        request : InferenceRequest
            Inference request containing opaque context reference and metadata.

        Returns
        -------
        InferenceResult
            Successful inference result with status SUCCEEDED.

        Raises
        ------
        OpenRouterError
            Provider-specific errors (auth, rate limit, timeout, etc.).

        Notes
        -----
        This implementation does not catch provider exceptions. They propagate
        to InferencePipeline according to the existing failure semantics.
        """
        started_at = datetime.now(timezone.utc)
        start_perf = time.perf_counter()

        # Build provider messages
        messages = build_inference_messages(
            context_reference=request.context_reference,
            product_key=request.product_key,
        )

        # Call OpenRouter
        structured_output = await self._client.complete(messages)

        # Map to domain findings
        findings = map_structured_output_to_findings(structured_output)

        # Measure duration
        finished_at = datetime.now(timezone.utc)
        duration = time.perf_counter() - start_perf

        # Build execution trace
        trace = ExecutionTrace(
            started_at=started_at,
            finished_at=finished_at,
            adapter_name=self.name,
            adapter_version=self.version,
            runtime_version=RUNTIME_VERSION,
            product_key=request.product_key,
        )

        # Build runtime metadata
        runtime_metadata = {
            "provider": "openrouter",
            "model": self._client.model,
            "base_url": self._client.base_url,
        }

        return InferenceResult(
            execution_id=request.execution_id,
            status=InferenceStatus.SUCCEEDED,
            findings=findings,
            execution_trace=trace,
            duration=duration,
            runtime_metadata=runtime_metadata,
        )
