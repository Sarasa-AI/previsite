"""Provider composition and registration helpers."""

from __future__ import annotations

from app.core.config import is_openrouter_api_key_configured, settings
from app.core.inference.application.registry import InferenceRegistry
from app.core.inference.infrastructure.providers.openrouter.adapter import (
    OpenRouterInferenceAdapter,
)
from app.core.inference.infrastructure.providers.openrouter.client import (
    OpenRouterClient,
)


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
