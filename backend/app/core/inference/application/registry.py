"""InferenceRegistry — maps product keys to adapters at composition time."""

from __future__ import annotations

from app.core.inference.application.adapter import InferenceAdapter


class InferenceRegistry:
    """Maps product_key → InferenceAdapter.

    Populated at application startup; no hardcoded product switches.
    """

    def __init__(self) -> None:
        self._adapters: dict[str, InferenceAdapter] = {}

    def register(self, product_key: str, adapter: InferenceAdapter) -> None:
        """Register an adapter for a product key.

        Raises ValueError if the key is already registered.
        """
        if product_key in self._adapters:
            raise ValueError(
                f"Adapter already registered for product_key={product_key!r}; "
                "unregister first or use a different key."
            )
        self._adapters[product_key] = adapter

    def resolve(self, product_key: str) -> InferenceAdapter:
        """Return the adapter registered for product_key.

        Raises KeyError with a clear message if no adapter is registered.
        """
        if product_key not in self._adapters:
            registered = ", ".join(sorted(self._adapters)) or "<none>"
            raise KeyError(
                f"No adapter registered for product_key={product_key!r}. "
                f"Registered products: {registered}"
            )
        return self._adapters[product_key]

    def registered_products(self) -> tuple[str, ...]:
        """Return an immutable snapshot of registered product keys."""
        return tuple(sorted(self._adapters))

    def clear(self) -> None:
        """Remove all registered adapters (for test isolation)."""
        self._adapters.clear()
