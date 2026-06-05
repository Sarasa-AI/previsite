import asyncio
import json

import httpx

from app.services.openrouter_service import (
    OpenRouterAuthenticationError,
    OpenRouterService,
    OpenRouterServiceError,
)


class _FakeMessage:
    def __init__(self, content: str):
        self.content = content


class _FakeChoice:
    def __init__(self, content: str):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content: str):
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, responses: list):
        self._responses = responses
        self._index = 0

    async def create(self, **_kwargs):
        if self._index >= len(self._responses):
            raise self._responses[-1]
        item = self._responses[self._index]
        self._index += 1
        if isinstance(item, Exception):
            raise item
        return _FakeResponse(item)


class _FakeChat:
    def __init__(self, responses: list):
        self.completions = _FakeCompletions(responses)


class _FakeClient:
    def __init__(self, responses: list):
        self.chat = _FakeChat(responses)


def _connection_error() -> Exception:
    from openai import APIConnectionError

    request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    return APIConnectionError(message="connection failed", request=request)


def test_generate_json_parses_json_object_response() -> None:
    async def run() -> None:
        service = OpenRouterService()
        payload = {
            "question_strategy": "acute",
            "questions": [
                {"id": "onset", "question": "از چه زمانی؟", "priority": 1, "red_flag_related": False}
            ],
        }
        service.client = _FakeClient([json.dumps(payload, ensure_ascii=False)])

        result = await service.generate_json("system", "user")
        assert result["question_strategy"] == "acute"
        assert len(result["questions"]) == 1

    asyncio.run(run())


def test_generate_json_strips_markdown_fences() -> None:
    async def run() -> None:
        service = OpenRouterService()
        payload = {
            "chief_complaint": "درد شکم",
            "hpi_summary": "خلاصه",
            "pertinent_positives": [],
            "pertinent_negatives": [],
            "red_flags": [],
        }
        fenced = f"```json\n{json.dumps(payload, ensure_ascii=False)}\n```"
        service.client = _FakeClient([fenced])

        result = await service.generate_json("system", "user")
        assert result["chief_complaint"] == "درد شکم"

    asyncio.run(run())


def test_generate_json_raises_on_invalid_json() -> None:
    async def run() -> None:
        service = OpenRouterService()
        service.client = _FakeClient(["not valid json at all"])

        try:
            await service.generate_json("system", "user")
            raise AssertionError("Expected OpenRouterServiceError")
        except OpenRouterServiceError as exc:
            assert "Failed to parse JSON" in str(exc)

    asyncio.run(run())


def test_generate_json_raises_on_api_connection_error() -> None:
    async def run() -> None:
        service = OpenRouterService()
        attempts = len(service._model_candidates()) * 2
        service.client = _FakeClient([_connection_error()] * attempts)

        try:
            await service.generate_json("system", "user")
            raise AssertionError("Expected OpenRouterServiceError")
        except OpenRouterServiceError as exc:
            assert "OpenRouter API request failed" in str(exc)

    asyncio.run(run())


def test_ensure_client_requires_api_key(monkeypatch) -> None:
    from app.core import config as config_module

    monkeypatch.setattr(config_module.settings, "openrouter_api_key", None)
    service = OpenRouterService()

    try:
        service._ensure_client()
        raise AssertionError("Expected OpenRouterAuthenticationError")
    except OpenRouterAuthenticationError as exc:
        assert "OPENROUTER_API_KEY" in str(exc)
