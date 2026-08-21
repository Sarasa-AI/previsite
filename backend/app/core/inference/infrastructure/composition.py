"""Provider composition and registration helpers."""

from __future__ import annotations

from app.core.config import is_openrouter_api_key_configured, settings
from app.core.inference.application.registry import InferenceRegistry
from app.core.inference.application.pipeline import InferencePipeline
from app.core.inference.application.publisher import NoOpInferenceResultPublisher
from app.core.inference.infrastructure.providers.openrouter.adapter import (
    OpenRouterInferenceAdapter,
)
from app.core.inference.infrastructure.providers.openrouter.client import (
    OpenRouterClient,
)


# Global inference registry and pipeline instances
_inference_registry: InferenceRegistry | None = None
_inference_pipeline: InferencePipeline | None = None


def create_openrouter_adapter() -> OpenRouterInferenceAdapter:
    """Create a configured OpenRouter inference adapter.

    Returns
    -------
    OpenRouterInferenceAdapter
        Configured adapter ready for inference.

    Raises
    ------
    ValueError
        If OpenRouter API key is not configured or is a placeholder.

    Notes
    -----
    This factory validates configuration at construction time to fail fast.
    """
    if not is_openrouter_api_key_configured():
        raise ValueError(
            "OpenRouter API key is not configured. "
            "Set OPENROUTER_API_KEY to a valid key to use the OpenRouter inference adapter."
        )

    client = OpenRouterClient(
        api_key=settings.openrouter_api_key or "",
        base_url=settings.openrouter_base_url,
        model=settings.openrouter_default_model,
        timeout=settings.openrouter_inference_timeout,
        http_referer=settings.openrouter_http_referer,
        app_title=settings.openrouter_app_title,
    )

    return OpenRouterInferenceAdapter(client)


def register_openrouter_adapter(
    registry: InferenceRegistry,
    product_key: str,
) -> None:
    """Register the OpenRouter adapter for a product key.

    Parameters
    ----------
    registry : InferenceRegistry
        Target registry.
    product_key : str
        Product identifier to associate with the adapter.

    Raises
    ------
    ValueError
        If configuration is invalid or product_key is already registered.

    Notes
    -----
    This does not modify global state. The caller controls registration timing
    and scope through the provided registry instance.
    """
    adapter = create_openrouter_adapter()
    registry.register(product_key, adapter)


def init_inference_runtime() -> tuple[InferenceRegistry, InferencePipeline]:
    """Initialize the global inference registry and pipeline.

    Returns
    -------
    tuple[InferenceRegistry, InferencePipeline]
        The initialized registry and pipeline instances.

    Notes
    -----
    This should be called once at application startup. Registers the OpenRouter
    adapter for the default product key if configured.
    """
    global _inference_registry, _inference_pipeline

    registry = InferenceRegistry()

    # Register OpenRouter adapter if configured
    if is_openrouter_api_key_configured():
        try:
            # Use a generic product key for general clinical inference
            register_openrouter_adapter(registry, "clinical_general")
            register_openrouter_adapter(registry, "document_intelligence")
            register_openrouter_adapter(registry, "soap_generation")
        except ValueError as exc:
            # Log but don't fail startup - inference is optional
            import logging
            logging.getLogger(__name__).warning(
                "Failed to register OpenRouter adapter: %s", exc
            )

    pipeline = InferencePipeline(registry, NoOpInferenceResultPublisher())

    _inference_registry = registry
    _inference_pipeline = pipeline

    return registry, pipeline


def get_inference_registry() -> InferenceRegistry:
    """Get the global inference registry (initialized at startup)."""
    if _inference_registry is None:
        raise RuntimeError(
            "Inference runtime not initialized. Call init_inference_runtime() at startup."
        )
    return _inference_registry


def get_inference_pipeline() -> InferencePipeline:
    """Get the global inference pipeline (initialized at startup)."""
    if _inference_pipeline is None:
        raise RuntimeError(
            "Inference runtime not initialized. Call init_inference_runtime() at startup."
        )
    return _inference_pipeline


async def close_inference_runtime() -> None:
    """Close the inference runtime (for graceful shutdown)."""
    global _inference_registry, _inference_pipeline
    _inference_registry = None
    _inference_pipeline = None
