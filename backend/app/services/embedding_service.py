import logging
import re
from typing import List

import ollama

from app.core.config import settings

logger = logging.getLogger(__name__)

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?؟])\s+")


class EmbeddingServiceError(Exception):
    """Raised when Ollama embedding generation fails."""


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

    async def generate_embedding(self, text: str) -> List[float]:
        prompt = text.strip()
        if not prompt:
            raise ValueError("Cannot generate embedding for empty text.")

        try:
            response = await self._client.embeddings(
                model=settings.embedding_model,
                prompt=prompt,
            )
        except Exception as exc:
            logger.exception("Ollama embedding request failed")
            raise EmbeddingServiceError(
                f"Failed to generate embedding with model {settings.embedding_model}"
            ) from exc

        embedding = response.get("embedding")
        if not embedding:
            raise EmbeddingServiceError("Ollama returned an empty embedding vector.")

        if len(embedding) != settings.embedding_dimensions:
            raise EmbeddingServiceError(
                f"Expected {settings.embedding_dimensions}-dim vector, got {len(embedding)}."
            )

        return embedding

    def chunk_medical_text(self, text: str, max_tokens: int | None = None) -> List[str]:
        return chunk_medical_text(text, max_tokens=max_tokens)

    async def generate_chunked_embeddings(
        self, text: str, max_tokens: int | None = None
    ) -> List[List[float]]:
        chunks = self.chunk_medical_text(text, max_tokens=max_tokens)
        if not chunks:
            raise ValueError("Cannot generate embeddings for empty text.")

        embeddings: List[List[float]] = []
        for chunk in chunks:
            embeddings.append(await self.generate_embedding(chunk))
        return embeddings


embedding_service = EmbeddingService()

generate_embedding = embedding_service.generate_embedding
generate_chunked_embeddings = embedding_service.generate_chunked_embeddings
