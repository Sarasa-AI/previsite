"""Tests for OpenRouter inference adapter."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from pydantic import ValidationError

from app.core.inference.application.adapter import InferenceAdapter
from app.core.inference.application.pipeline import InferencePipeline
from app.core.inference.application.registry import InferenceRegistry
from app.core.inference.domain.enums import InferenceStatus
from app.core.inference.domain.models import InferenceRequest
from app.core.inference.infrastructure import RUNTIME_VERSION
from app.core.inference.infrastructure.composition import (
    create_openrouter_adapter,
    register_openrouter_adapter,
)
from app.core.inference.infrastructure.providers.openrouter.adapter import (
    OpenRouterInferenceAdapter,
)
from app.core.inference.infrastructure.providers.openrouter.client import (
    OpenRouterClient,
)
from app.core.inference.infrastructure.providers.openrouter.errors import (
    OpenRouterAuthError,
    OpenRouterHTTPError,
    OpenRouterRateLimitError,
    OpenRouterResponseError,
    OpenRouterStructuredOutputError,
    OpenRouterTimeoutError,
    OpenRouterTransportError,
)
from app.core.inference.infrastructure.providers.openrouter.mapper import (
    map_structured_output_to_findings,
)
from app.core.inference.infrastructure.providers.openrouter.models import (
    OpenRouterChoice,
    OpenRouterChoiceMessage,
    OpenRouterCompletionResponse,
    OpenRouterMessage,
    OpenRouterProviderFinding,
    OpenRouterStructuredOutput,
    OpenRouterUsage,
)
from app.core.inference.infrastructure.providers.openrouter.prompts import (
    build_inference_messages,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_httpx_client():
    """Mock httpx.AsyncClient."""
    client = AsyncMock(spec=httpx.AsyncClient)
    return client


@pytest.fixture
def openrouter_client(mock_httpx_client):
    """OpenRouterClient with mocked transport."""
    client = OpenRouterClient(
        api_key="sk-or-test-key",
        base_url="https://openrouter.ai/api/v1",
        model="test-model",
        timeout=30.0,
        http_referer="http://test",
        app_title="Test",
    )
    client._client = mock_httpx_client
    return client


@pytest.fixture
def inference_request():
    """Sample InferenceRequest."""
    return InferenceRequest.create(
        session_id=1,
        product_key="test-product",
        context_reference="ctx-ref-001",
    )


# ---------------------------------------------------------------------------
# Client — construction
# ---------------------------------------------------------------------------


class TestClientConstruction:
    def test_empty_api_key_rejected(self):
        with pytest.raises(ValueError, match="API key must not be empty"):
            OpenRouterClient(
                api_key="",
                base_url="https://openrouter.ai/api/v1",
                model="test-model",
                timeout=30.0,
                http_referer="http://test",
                app_title="Test",
            )

    def test_none_api_key_rejected(self):
        with pytest.raises(ValueError, match="API key must not be empty"):
            OpenRouterClient(
                api_key=None,  # type: ignore
                base_url="https://openrouter.ai/api/v1",
                model="test-model",
                timeout=30.0,
                http_referer="http://test",
                app_title="Test",
            )

    def test_whitespace_api_key_rejected(self):
        with pytest.raises(ValueError, match="API key must not be empty"):
            OpenRouterClient(
                api_key="   ",
                base_url="https://openrouter.ai/api/v1",
                model="test-model",
                timeout=30.0,
                http_referer="http://test",
                app_title="Test",
            )

    def test_valid_construction(self):
        client = OpenRouterClient(
            api_key="sk-or-valid-key",
            base_url="https://openrouter.ai/api/v1",
            model="test-model",
            timeout=30.0,
            http_referer="http://test",
            app_title="Test",
        )
        assert client.model == "test-model"
        assert client.base_url == "https://openrouter.ai/api/v1"


# ---------------------------------------------------------------------------
# Client — successful completion
# ---------------------------------------------------------------------------


class TestClientSuccess:
    @pytest.mark.asyncio
    async def test_successful_completion(self, openrouter_client, mock_httpx_client):
        response_payload = {
            "id": "gen-123",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "test-model",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": json.dumps(
                            {
                                "findings": [
                                    {
                                        "finding_key": "f001",
                                        "artifact_type": "clinical_finding",
                                        "title": "Test Finding",
                                        "summary": "Test summary",
                                        "confidence": 0.95,
                                        "attributes": {},
                                    }
                                ]
                            }
                        ),
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        }

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = response_payload
        mock_httpx_client.post.return_value = mock_response

        messages = (
            OpenRouterMessage(role="system", content="System prompt"),
            OpenRouterMessage(role="user", content="User prompt"),
        )

        result = await openrouter_client.complete(messages)

        assert isinstance(result, OpenRouterStructuredOutput)
        assert len(result.findings) == 1
        assert result.findings[0].finding_key == "f001"
        assert result.findings[0].confidence == 0.95

    @pytest.mark.asyncio
    async def test_empty_findings_is_valid(self, openrouter_client, mock_httpx_client):
        response_payload = {
            "id": "gen-456",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "test-model",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": json.dumps({"findings": []}),
                    },
                    "finish_reason": "stop",
                }
            ],
        }

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = response_payload
        mock_httpx_client.post.return_value = mock_response

        messages = (OpenRouterMessage(role="user", content="Test"),)

        result = await openrouter_client.complete(messages)

        assert isinstance(result, OpenRouterStructuredOutput)
        assert len(result.findings) == 0


# ---------------------------------------------------------------------------
# Client — HTTP errors
# ---------------------------------------------------------------------------


class TestClientHTTPErrors:
    @pytest.mark.asyncio
    async def test_401_raises_auth_error(self, openrouter_client, mock_httpx_client):
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 401
        mock_httpx_client.post.return_value = mock_response

        messages = (OpenRouterMessage(role="user", content="Test"),)

        with pytest.raises(OpenRouterAuthError, match="401 Unauthorized"):
            await openrouter_client.complete(messages)

    @pytest.mark.asyncio
    async def test_429_raises_rate_limit_error(self, openrouter_client, mock_httpx_client):
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 429
        mock_response.headers = httpx.Headers({"retry-after": "60"})
        mock_httpx_client.post.return_value = mock_response

        messages = (OpenRouterMessage(role="user", content="Test"),)

        with pytest.raises(OpenRouterRateLimitError, match="429 Too Many Requests") as exc_info:
            await openrouter_client.complete(messages)

        assert exc_info.value.retry_after == 60

    @pytest.mark.asyncio
    async def test_429_without_retry_after(self, openrouter_client, mock_httpx_client):
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 429
        mock_response.headers = httpx.Headers({})
        mock_httpx_client.post.return_value = mock_response

        messages = (OpenRouterMessage(role="user", content="Test"),)

        with pytest.raises(OpenRouterRateLimitError) as exc_info:
            await openrouter_client.complete(messages)

        assert exc_info.value.retry_after is None

    @pytest.mark.asyncio
    async def test_500_raises_http_error(self, openrouter_client, mock_httpx_client):
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_httpx_client.post.return_value = mock_response

        messages = (OpenRouterMessage(role="user", content="Test"),)

        with pytest.raises(OpenRouterHTTPError, match="HTTP error 500") as exc_info:
            await openrouter_client.complete(messages)

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_timeout_raises_timeout_error(self, openrouter_client, mock_httpx_client):
        mock_httpx_client.post.side_effect = httpx.TimeoutException("Timeout")

        messages = (OpenRouterMessage(role="user", content="Test"),)

        with pytest.raises(OpenRouterTimeoutError, match="timed out"):
            await openrouter_client.complete(messages)

    @pytest.mark.asyncio
    async def test_connect_error_raises_transport_error(
        self, openrouter_client, mock_httpx_client
    ):
        mock_httpx_client.post.side_effect = httpx.ConnectError("Connection failed")

        messages = (OpenRouterMessage(role="user", content="Test"),)

        with pytest.raises(OpenRouterTransportError, match="transport failure"):
            await openrouter_client.complete(messages)

    @pytest.mark.asyncio
    async def test_network_error_raises_transport_error(
        self, openrouter_client, mock_httpx_client
    ):
        mock_httpx_client.post.side_effect = httpx.NetworkError("Network issue")

        messages = (OpenRouterMessage(role="user", content="Test"),)

        with pytest.raises(OpenRouterTransportError, match="transport failure"):
            await openrouter_client.complete(messages)


# ---------------------------------------------------------------------------
# Client — malformed responses
# ---------------------------------------------------------------------------


class TestClientMalformedResponses:
    @pytest.mark.asyncio
    async def test_invalid_json_raises_response_error(
        self, openrouter_client, mock_httpx_client
    ):
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid", "", 0)
        mock_httpx_client.post.return_value = mock_response

        messages = (OpenRouterMessage(role="user", content="Test"),)

        with pytest.raises(OpenRouterResponseError, match="Failed to parse JSON"):
            await openrouter_client.complete(messages)

    @pytest.mark.asyncio
    async def test_empty_choices_raises_response_error(
        self, openrouter_client, mock_httpx_client
    ):
        response_payload = {
            "id": "gen-789",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "test-model",
            "choices": [],
        }

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = response_payload
        mock_httpx_client.post.return_value = mock_response

        messages = (OpenRouterMessage(role="user", content="Test"),)

        with pytest.raises(OpenRouterResponseError, match="no choices"):
            await openrouter_client.complete(messages)

    @pytest.mark.asyncio
    async def test_empty_content_raises_response_error(
        self, openrouter_client, mock_httpx_client
    ):
        response_payload = {
            "id": "gen-empty",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "test-model",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": ""},
                    "finish_reason": "stop",
                }
            ],
        }

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = response_payload
        mock_httpx_client.post.return_value = mock_response

        messages = (OpenRouterMessage(role="user", content="Test"),)

        with pytest.raises(OpenRouterResponseError, match="content is empty"):
            await openrouter_client.complete(messages)

    @pytest.mark.asyncio
    async def test_invalid_structured_json_raises_error(
        self, openrouter_client, mock_httpx_client
    ):
        response_payload = {
            "id": "gen-bad",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "test-model",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "not valid json",
                    },
                    "finish_reason": "stop",
                }
            ],
        }

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = response_payload
        mock_httpx_client.post.return_value = mock_response

        messages = (OpenRouterMessage(role="user", content="Test"),)

        with pytest.raises(OpenRouterStructuredOutputError, match="not valid JSON"):
            await openrouter_client.complete(messages)

    @pytest.mark.asyncio
    async def test_invalid_schema_raises_structured_output_error(
        self, openrouter_client, mock_httpx_client
    ):
        response_payload = {
            "id": "gen-schema",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "test-model",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": json.dumps({"wrong_field": "value"}),
                    },
                    "finish_reason": "stop",
                }
            ],
        }

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = response_payload
        mock_httpx_client.post.return_value = mock_response

        messages = (OpenRouterMessage(role="user", content="Test"),)

        with pytest.raises(OpenRouterStructuredOutputError, match="does not match expected schema"):
            await openrouter_client.complete(messages)


# ---------------------------------------------------------------------------
# Mapper
# ---------------------------------------------------------------------------


class TestMapper:
    def test_valid_mapping(self):
        provider_finding = OpenRouterProviderFinding(
            finding_key="f001",
            artifact_type="clinical_finding",
            title="Test Finding",
            summary="Test summary",
            confidence=0.9,
            attributes={"key": "value"},
        )

        structured_output = OpenRouterStructuredOutput(findings=(provider_finding,))

        domain_findings = map_structured_output_to_findings(structured_output)

        assert len(domain_findings) == 1
        assert domain_findings[0].finding_key == "f001"
        assert domain_findings[0].artifact_type == "clinical_finding"
        assert domain_findings[0].title == "Test Finding"
        assert domain_findings[0].summary == "Test summary"
        assert domain_findings[0].confidence == 0.9
        assert domain_findings[0].attributes == {"key": "value"}

    def test_empty_findings(self):
        structured_output = OpenRouterStructuredOutput(findings=())

        domain_findings = map_structured_output_to_findings(structured_output)

        assert len(domain_findings) == 0

    def test_multiple_findings(self):
        provider_findings = (
            OpenRouterProviderFinding(
                finding_key="f001",
                artifact_type="clinical_finding",
                title="Finding 1",
                summary="Summary 1",
            ),
            OpenRouterProviderFinding(
                finding_key="f002",
                artifact_type="clinical_finding",
                title="Finding 2",
                summary="Summary 2",
            ),
        )

        structured_output = OpenRouterStructuredOutput(findings=provider_findings)

        domain_findings = map_structured_output_to_findings(structured_output)

        assert len(domain_findings) == 2
        assert domain_findings[0].finding_key == "f001"
        assert domain_findings[1].finding_key == "f002"

    def test_invalid_domain_validation_raises_error(self):
        # Invalid confidence > 1.0 should fail domain validation
        provider_finding = OpenRouterProviderFinding(
            finding_key="f001",
            artifact_type="clinical_finding",
            title="Test Finding",
            summary="Test summary",
            confidence=1.5,  # Invalid
            attributes={},
        )

        structured_output = OpenRouterStructuredOutput(findings=(provider_finding,))

        with pytest.raises(OpenRouterStructuredOutputError, match="Failed to map"):
            map_structured_output_to_findings(structured_output)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------


class TestPrompts:
    def test_build_inference_messages(self):
        messages = build_inference_messages(
            context_reference="ctx-ref-123",
            product_key="test-product",
        )

        assert len(messages) == 2
        assert messages[0].role == "system"
        assert "structured inference" in messages[0].content.lower()
        assert messages[1].role == "user"
        assert "ctx-ref-123" in messages[1].content
        assert "test-product" in messages[1].content


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class TestAdapter:
    @pytest.mark.asyncio
    async def test_successful_inference(self, openrouter_client, mock_httpx_client, inference_request):
        response_payload = {
            "id": "gen-adapter",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "test-model",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": json.dumps(
                            {
                                "findings": [
                                    {
                                        "finding_key": "adapter-f001",
                                        "artifact_type": "clinical_finding",
                                        "title": "Adapter Test",
                                        "summary": "Adapter summary",
                                        "confidence": 0.85,
                                        "attributes": {},
                                    }
                                ]
                            }
                        ),
                    },
                }
            ],
        }

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = response_payload
        mock_httpx_client.post.return_value = mock_response

        adapter = OpenRouterInferenceAdapter(openrouter_client)

        result = await adapter.infer(inference_request)

        assert result.status == InferenceStatus.SUCCEEDED
        assert result.execution_id == inference_request.execution_id
        assert len(result.findings) == 1
        assert result.findings[0].finding_key == "adapter-f001"

    @pytest.mark.asyncio
    async def test_execution_trace(self, openrouter_client, mock_httpx_client, inference_request):
        response_payload = {
            "id": "gen-trace",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "test-model",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": json.dumps({"findings": []}),
                    },
                }
            ],
        }

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = response_payload
        mock_httpx_client.post.return_value = mock_response

        adapter = OpenRouterInferenceAdapter(openrouter_client)

        result = await adapter.infer(inference_request)

        trace = result.execution_trace
        assert trace.adapter_name == "openrouter"
        assert trace.adapter_version == "1.0.0"
        assert trace.runtime_version == RUNTIME_VERSION
        assert trace.product_key == inference_request.product_key

    @pytest.mark.asyncio
    async def test_runtime_metadata(self, openrouter_client, mock_httpx_client, inference_request):
        response_payload = {
            "id": "gen-meta",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "test-model",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": json.dumps({"findings": []}),
                    },
                }
            ],
        }

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = response_payload
        mock_httpx_client.post.return_value = mock_response

        adapter = OpenRouterInferenceAdapter(openrouter_client)

        result = await adapter.infer(inference_request)

        assert result.runtime_metadata["provider"] == "openrouter"
        assert result.runtime_metadata["model"] == "test-model"
        assert result.runtime_metadata["base_url"] == "https://openrouter.ai/api/v1"

    @pytest.mark.asyncio
    async def test_provider_exception_propagates(
        self, openrouter_client, mock_httpx_client, inference_request
    ):
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 401
        mock_httpx_client.post.return_value = mock_response

        adapter = OpenRouterInferenceAdapter(openrouter_client)

        with pytest.raises(OpenRouterAuthError):
            await adapter.infer(inference_request)

    def test_protocol_compliance(self, openrouter_client):
        adapter = OpenRouterInferenceAdapter(openrouter_client)
        assert isinstance(adapter, InferenceAdapter)

    def test_adapter_properties(self, openrouter_client):
        adapter = OpenRouterInferenceAdapter(openrouter_client)
        assert adapter.name == "openrouter"
        assert adapter.version == "1.0.0"


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------


class TestComposition:
    def test_create_adapter_with_valid_config(self, monkeypatch):
        from app.core import config as config_module

        monkeypatch.setattr(config_module.settings, "openrouter_api_key", "sk-or-valid-key")
        monkeypatch.setattr(
            config_module.settings, "openrouter_base_url", "https://openrouter.ai/api/v1"
        )
        monkeypatch.setattr(config_module.settings, "openrouter_default_model", "test-model")
        monkeypatch.setattr(config_module.settings, "openrouter_inference_timeout", 30.0)
        monkeypatch.setattr(config_module.settings, "openrouter_http_referer", "http://test")
        monkeypatch.setattr(config_module.settings, "openrouter_app_title", "Test")

        adapter = create_openrouter_adapter()

        assert isinstance(adapter, OpenRouterInferenceAdapter)
        assert adapter.name == "openrouter"

    def test_create_adapter_missing_key_rejected(self, monkeypatch):
        from app.core import config as config_module

        monkeypatch.setattr(config_module.settings, "openrouter_api_key", None)

        with pytest.raises(ValueError, match="API key is not configured"):
            create_openrouter_adapter()

    def test_create_adapter_placeholder_key_rejected(self, monkeypatch):
        from app.core import config as config_module

        monkeypatch.setattr(config_module.settings, "openrouter_api_key", "your-openrouter-api-key")

        with pytest.raises(ValueError, match="API key is not configured"):
            create_openrouter_adapter()

    def test_register_openrouter_adapter(self, monkeypatch):
        from app.core import config as config_module

        monkeypatch.setattr(config_module.settings, "openrouter_api_key", "sk-or-valid-key")
        monkeypatch.setattr(
            config_module.settings, "openrouter_base_url", "https://openrouter.ai/api/v1"
        )
        monkeypatch.setattr(config_module.settings, "openrouter_default_model", "test-model")
        monkeypatch.setattr(config_module.settings, "openrouter_inference_timeout", 30.0)
        monkeypatch.setattr(config_module.settings, "openrouter_http_referer", "http://test")
        monkeypatch.setattr(config_module.settings, "openrouter_app_title", "Test")

        registry = InferenceRegistry()

        register_openrouter_adapter(registry, "test-product")

        adapter = registry.resolve("test-product")
        assert isinstance(adapter, OpenRouterInferenceAdapter)


# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------


class TestSecurity:
    @pytest.mark.asyncio
    async def test_api_key_not_in_exception_message(
        self, openrouter_client, mock_httpx_client
    ):
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 401
        mock_httpx_client.post.return_value = mock_response

        messages = (OpenRouterMessage(role="user", content="Test"),)

        with pytest.raises(OpenRouterAuthError) as exc_info:
            await openrouter_client.complete(messages)

        assert "sk-or-test-key" not in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_api_key_not_in_runtime_metadata(
        self, openrouter_client, mock_httpx_client, inference_request
    ):
        response_payload = {
            "id": "gen-sec",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "test-model",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": json.dumps({"findings": []}),
                    },
                }
            ],
        }

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = response_payload
        mock_httpx_client.post.return_value = mock_response

        adapter = OpenRouterInferenceAdapter(openrouter_client)

        result = await adapter.infer(inference_request)

        metadata_str = json.dumps(result.runtime_metadata)
        assert "sk-or-test-key" not in metadata_str
        assert "api_key" not in metadata_str.lower()


# ---------------------------------------------------------------------------
# Pipeline integration
# ---------------------------------------------------------------------------


class TestPipelineIntegration:
    @pytest.mark.asyncio
    async def test_adapter_in_pipeline(self, openrouter_client, mock_httpx_client):
        response_payload = {
            "id": "gen-pipeline",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "test-model",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": json.dumps(
                            {
                                "findings": [
                                    {
                                        "finding_key": "pipeline-f001",
                                        "artifact_type": "clinical_finding",
                                        "title": "Pipeline Test",
                                        "summary": "Pipeline summary",
                                        "confidence": 0.9,
                                        "attributes": {},
                                    }
                                ]
                            }
                        ),
                    },
                }
            ],
        }

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = response_payload
        mock_httpx_client.post.return_value = mock_response

        adapter = OpenRouterInferenceAdapter(openrouter_client)
        registry = InferenceRegistry()
        registry.register("test-product", adapter)
        pipeline = InferencePipeline(registry)

        request = InferenceRequest.create(
            session_id=1,
            product_key="test-product",
            context_reference="ctx-pipeline",
        )

        result = await pipeline.execute(request)

        assert result.status == InferenceStatus.SUCCEEDED
        assert len(result.findings) == 1
        assert result.findings[0].finding_key == "pipeline-f001"
        assert result.execution_trace.product_key == "test-product"

