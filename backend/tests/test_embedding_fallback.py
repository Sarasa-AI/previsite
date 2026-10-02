from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core import config as config_module
from app.services.embedding_service import EmbeddingService, EmbeddingServiceError


@pytest.fixture
def service(monkeypatch):
    monkeypatch.setattr(config_module.settings, "embedding_dimensions", 768)
    monkeypatch.setattr(
        config_module.settings, "openrouter_embedding_model", "openai/text-embedding-3-small"
    )
    monkeypatch.setattr(config_module.settings, "openrouter_base_url", "https://openrouter.ai/api/v1")
    monkeypatch.setattr(config_module.settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(config_module.settings, "openrouter_http_referer", "https://example.test")
    monkeypatch.setattr(config_module.settings, "openrouter_app_title", "PreVisit Test")
    return EmbeddingService()


@pytest.mark.asyncio
async def test_openrouter_provider_posts_embeddings_with_dimensions(service, monkeypatch):
    """OpenRouter embeddings include the dimensions parameter matching pgvector schema."""
    monkeypatch.setattr(config_module.settings, "embedding_provider", "openrouter")
    vector = [0.02] * 768

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"data": [{"embedding": vector}]}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.services.embedding_service.httpx.AsyncClient", return_value=mock_client):
        result = await service.generate_embedding("chunk text")

    assert result == vector
    kwargs = mock_client.post.await_args.kwargs
    assert kwargs["json"]["dimensions"] == 768
    assert kwargs["json"]["model"] == "openai/text-embedding-3-small"


@pytest.mark.asyncio
async def test_openrouter_embedding_validates_dimensions(service, monkeypatch):
    """Embeddings from OpenRouter must match the configured dimensions (768 for pgvector)."""
    monkeypatch.setattr(config_module.settings, "embedding_provider", "openrouter")
    # Wrong dimension - should raise
    vector = [0.02] * 512

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"data": [{"embedding": vector}]}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.services.embedding_service.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(EmbeddingServiceError, match="Expected 768-dim vector"):
            await service.generate_embedding("chunk text")


@pytest.mark.asyncio
async def test_embedding_provider_openrouter_does_not_attempt_ollama(service, monkeypatch):
    """With embedding_provider=openrouter, no Ollama code path is executed."""
    monkeypatch.setattr(config_module.settings, "embedding_provider", "openrouter")
    vector = [0.01] * 768

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"data": [{"embedding": vector}]}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.services.embedding_service.httpx.AsyncClient", return_value=mock_client):
        result = await service.generate_embedding("test text")

    assert result == vector
    # Verify only one call was made to OpenRouter
    assert mock_client.post.await_count == 1


@pytest.mark.asyncio
async def test_embedding_provider_auto_uses_openrouter_directly(service, monkeypatch):
    """With embedding_provider=auto (now default), OpenRouter is used directly - no Ollama fallback."""
    monkeypatch.setattr(config_module.settings, "embedding_provider", "auto")
    vector = [0.01] * 768

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"data": [{"embedding": vector}]}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.services.embedding_service.httpx.AsyncClient", return_value=mock_client):
        result = await service.generate_embedding("test text")

    assert result == vector
    # Verify only one call was made to OpenRouter
    assert mock_client.post.await_count == 1


@pytest.mark.asyncio
async def test_generate_embedding_raises_on_empty_text(service):
    """Empty text should raise ValueError."""
    with pytest.raises(ValueError, match="Cannot generate embedding for empty text"):
        await service.generate_embedding("")


@pytest.mark.asyncio
async def test_generate_embedding_raises_on_missing_openrouter_key(service, monkeypatch):
    """Missing OpenRouter API key should raise EmbeddingServiceError."""
    monkeypatch.setattr(config_module.settings, "openrouter_api_key", "")
    monkeypatch.setattr(config_module.settings, "embedding_provider", "openrouter")

    with pytest.raises(EmbeddingServiceError, match="OpenRouter embedding fallback is not configured"):
        await service.generate_embedding("some text")


@pytest.mark.asyncio
async def test_chunk_medical_text_basic(service):
    """Text chunking works for medical text."""
    text = "Patient has hypertension. They also have diabetes. Both are controlled."
    chunks = service.chunk_medical_text(text, max_tokens=10)
    assert len(chunks) >= 1
    assert all(isinstance(c, str) for c in chunks)
