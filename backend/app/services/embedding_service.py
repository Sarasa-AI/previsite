import logging
import re
from typing import List

import httpx
import ollama

from app.core.config import is_openrouter_api_key_configured, settings

logger = logging.getLogger(__name__)

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?؟])\s+")


class EmbeddingServiceError(Exception):
    """Raised when embedding generation fails for all configured providers."""


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _hard_split(text: str, max_tokens: int) -> List[str]:
    char_budget = max_tokens * 4
    return [text[i : i + char_budget] for i in range(0, len(text), char_budget)]


def _split_into_units(text: str, max_tokens: int) -> List[str]:
    stripped = text.strip()
    if not stripped:
        return []

    if _estimate_tokens(stripped) <= max_tokens:
        return [stripped]

    units: List[str] = []
    for paragraph in re.split(r"\n\s*\n", stripped):
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        if _estimate_tokens(paragraph) <= max_tokens:
            units.append(paragraph)
            continue

        for sentence in SENTENCE_SPLIT_RE.split(paragraph):
            sentence = sentence.strip()
            if not sentence:
                continue
            if _estimate_tokens(sentence) <= max_tokens:
                units.append(sentence)
            else:
                units.extend(_hard_split(sentence, max_tokens))

    return units


def _merge_units(units: List[str], max_tokens: int) -> List[str]:
    if not units:
        return []

    chunks: List[str] = []
    current = units[0]

    for unit in units[1:]:
        candidate = f"{current}\n\n{unit}"
        if _estimate_tokens(candidate) <= max_tokens:
            current = candidate
        else:
            chunks.append(current)
            current = unit

    chunks.append(current)
    return chunks


def chunk_medical_text(text: str, max_tokens: int | None = None) -> List[str]:
    """Split long medical text into chunks suitable for embedding."""
    token_limit = max_tokens if max_tokens is not None else settings.max_embedding_tokens
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []

    units = _split_into_units(normalized, token_limit)
    return _merge_units(units, token_limit)


class EmbeddingService:
    def __init__(self) -> None:
        self._client = ollama.AsyncClient(host=settings.ollama_host)

    def _validate_dimensions(self, embedding: List[float], *, provider: str) -> List[float]:
        if not embedding:
            raise EmbeddingServiceError(f"{provider} returned an empty embedding vector.")
        if len(embedding) != settings.embedding_dimensions:
            raise EmbeddingServiceError(
                f"Expected {settings.embedding_dimensions}-dim vector from {provider}, "
                f"got {len(embedding)}."
            )
        return embedding

    async def _embed_with_ollama(self, prompt: str) -> List[float]:
        try:
            response = await self._client.embeddings(
                model=settings.embedding_model,
                prompt=prompt,
            )
        except Exception as exc:
            logger.warning("Ollama embedding request failed: %s", exc)
            raise EmbeddingServiceError(
                f"Failed to generate embedding with Ollama model {settings.embedding_model}"
            ) from exc

        embedding = response.get("embedding") if isinstance(response, dict) else None
        if embedding is None and hasattr(response, "embedding"):
            embedding = response.embedding
        return self._validate_dimensions(list(embedding or []), provider="Ollama")

    async def _embed_with_openrouter(self, prompt: str) -> List[float]:
        if not is_openrouter_api_key_configured():
            raise EmbeddingServiceError(
                "OpenRouter embedding fallback is not configured (OPENROUTER_API_KEY missing)."
            )

        url = settings.openrouter_base_url.rstrip("/") + "/embeddings"
        headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": settings.openrouter_http_referer,
            "X-Title": settings.openrouter_app_title,
        }
        payload = {
            "model": settings.openrouter_embedding_model,
            "input": prompt,
            "dimensions": settings.embedding_dimensions,
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                body = response.json()
        except Exception as exc:
            logger.warning("OpenRouter embedding request failed: %s", exc)
            raise EmbeddingServiceError(
                f"Failed to generate embedding with OpenRouter model "
                f"{settings.openrouter_embedding_model}"
            ) from exc

        try:
            embedding = body["data"][0]["embedding"]
        except (KeyError, IndexError, TypeError) as exc:
            raise EmbeddingServiceError(
                "OpenRouter returned an unexpected embeddings response shape."
            ) from exc

        return self._validate_dimensions(list(embedding), provider="OpenRouter")

    async def generate_embedding(self, text: str) -> List[float]:
        prompt = text.strip()
        if not prompt:
            raise ValueError("Cannot generate embedding for empty text.")

        provider = (settings.embedding_provider or "auto").strip().lower()
        errors: list[str] = []

        if provider == "ollama":
            return await self._embed_with_ollama(prompt)

        if provider == "openrouter":
            return await self._embed_with_openrouter(prompt)

        if provider != "auto":
            raise EmbeddingServiceError(
                f"Unknown EMBEDDING_PROVIDER={provider!r}. Use auto, ollama, or openrouter."
            )

        # auto: prefer Ollama, fall back to OpenRouter when Ollama is unreachable.
        try:
            return await self._embed_with_ollama(prompt)
        except EmbeddingServiceError as exc:
            errors.append(str(exc))
            logger.warning("Ollama embedding failed; attempting OpenRouter fallback")

        try:
            return await self._embed_with_openrouter(prompt)
        except EmbeddingServiceError as exc:
            errors.append(str(exc))

        raise EmbeddingServiceError(
            "All embedding providers failed. "
            + " | ".join(errors)
        )

    def chunk_medical_text(self, text: str, max_tokens: int | None = None) -> List[str]:
        return chunk_medical_text(text, max_tokens=max_tokens)


embedding_service = EmbeddingService()

generate_embedding = embedding_service.generate_embedding
