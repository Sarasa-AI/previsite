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
async def test_auto_falls_back_to_openrouter_when_ollama_fails(service, monkeypatch):
    monkeypatch.setattr(config_module.settings, "embedding_provider", "auto")
    vector = [0.01] * 768

    service._embed_with_ollama = AsyncMock(
        side_effect=EmbeddingServiceError("Failed to generate embedding with Ollama")
    )
    service._embed_with_openrouter = AsyncMock(return_value=vector)

    result = await service.generate_embedding("hypertension guideline excerpt")

    assert result == vector
    service._embed_with_ollama.assert_awaited_once()
    service._embed_with_openrouter.assert_awaited_once()


@pytest.mark.asyncio
async def test_auto_raises_when_all_providers_fail(service, monkeypatch):
    monkeypatch.setattr(config_module.settings, "embedding_provider", "auto")
    service._embed_with_ollama = AsyncMock(
        side_effect=EmbeddingServiceError("ollama down")
    )
    service._embed_with_openrouter = AsyncMock(
        side_effect=EmbeddingServiceError("openrouter down")
    )

    with pytest.raises(EmbeddingServiceError, match="All embedding providers failed"):
        await service.generate_embedding("sample text")


@pytest.mark.asyncio
async def test_openrouter_provider_posts_embeddings_with_dimensions(service, monkeypatch):
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
async def test_ollama_only_does_not_call_openrouter(service, monkeypatch):
    monkeypatch.setattr(config_module.settings, "embedding_provider", "ollama")
    vector = [0.03] * 768
    service._embed_with_ollama = AsyncMock(return_value=vector)
    service._embed_with_openrouter = AsyncMock()

    result = await service.generate_embedding("local only")

    assert result == vector
    service._embed_with_openrouter.assert_not_called()
