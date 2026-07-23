"""Optional CrossEncoder reranking for RAG retrieval candidates."""

from __future__ import annotations

import logging
from typing import Any, Protocol

from app.core.config import settings

logger = logging.getLogger(__name__)


class CrossEncoderLike(Protocol):
    def predict(self, pairs: list[list[str]]) -> Any: ...


class RerankerService:
    """Lazy-loaded CrossEncoder wrapper used to reorder vector-search hits."""

    def __init__(self) -> None:
        self._model: CrossEncoderLike | None = None

    @property
    def enabled(self) -> bool:
        return bool(settings.reranker_enabled)

    def _load_model(self) -> CrossEncoderLike:
        if self._model is None:
            from sentence_transformers import CrossEncoder

            logger.info("Loading CrossEncoder reranker model=%s", settings.reranker_model)
            self._model = CrossEncoder(settings.reranker_model)
        return self._model

    def set_model(self, model: CrossEncoderLike | None) -> None:
        """Test helper to inject a mock CrossEncoder."""
        self._model = model

    def rerank(
        self,
        query: str,
        candidates: list[dict],
        *,
        top_k: int,
    ) -> list[dict]:
        """
        Reorder candidates with a CrossEncoder and return the top_k results.

        Each candidate dict is expected to contain at least ``content``.
        Cosine ``confidence`` is preserved; ``rerank_score`` is added.
        """
        if not candidates or top_k <= 0:
            return []

        if not self.enabled:
            return candidates[:top_k]

        try:
            model = self._load_model()
            pairs = [[query, item.get("content") or ""] for item in candidates]
            scores = model.predict(pairs)
        except Exception:
            logger.exception("CrossEncoder rerank failed; falling back to cosine order")
            return candidates[:top_k]

        scored: list[tuple[float, dict]] = []
        for item, score in zip(candidates, scores):
            enriched = {**item, "rerank_score": float(score)}
            scored.append((float(score), enriched))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [item for _, item in scored[:top_k]]


reranker_service = RerankerService()
