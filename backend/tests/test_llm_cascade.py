import time

import pytest

from app.schemas.intake import HPIQuestionsResponse
from app.services.llm_cascade import llm_cascade
from app.services.llm_circuit_breaker import CircuitState, Tier1CircuitBreaker
from app.services.openrouter_service import OpenRouterServiceError


@pytest.fixture(autouse=True)
def reset_circuit_breaker():
    from app.services.llm_circuit_breaker import tier1_circuit_breaker

    tier1_circuit_breaker.reset()
    yield
    tier1_circuit_breaker.reset()


class TestTier1CircuitBreaker:
    @pytest.mark.asyncio
    async def test_opens_after_threshold_failures(self):
        breaker = Tier1CircuitBreaker(failure_threshold=3, cooldown_seconds=60)

        for i in range(3):
            await breaker.record_tier1_failure(Exception(f"fail-{i}"))

        assert breaker.state == CircuitState.OPEN
        assert await breaker.should_skip_tier1() is True

    @pytest.mark.asyncio
    async def test_half_open_after_cooldown(self):
        breaker = Tier1CircuitBreaker(failure_threshold=1, cooldown_seconds=0)
        await breaker.record_tier1_failure(Exception("fail"))
        assert breaker.state == CircuitState.OPEN

        breaker._opened_at = time.monotonic() - 1
        assert await breaker.should_skip_tier1() is False
        assert breaker.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_half_open_success_closes_circuit(self):
        breaker = Tier1CircuitBreaker(failure_threshold=1, cooldown_seconds=0)
        await breaker.record_tier1_failure(Exception("fail"))
        breaker._opened_at = time.monotonic() - 1
        await breaker.should_skip_tier1()

        await breaker.record_tier1_success()
        assert breaker.state == CircuitState.CLOSED
        assert await breaker.should_skip_tier1() is False

    @pytest.mark.asyncio
    async def test_half_open_failure_reopens_circuit(self):
        breaker = Tier1CircuitBreaker(failure_threshold=1, cooldown_seconds=60)
        await breaker.record_tier1_failure(Exception("fail"))
        breaker._state = CircuitState.HALF_OPEN

        await breaker.record_tier1_failure(Exception("probe-fail"))
        assert breaker.state == CircuitState.OPEN


class TestLLMCascade:
    @pytest.mark.asyncio
    async def test_tier1_success(self, monkeypatch):
        async def fake_tier1(*_args, **_kwargs):
            return {
                "question_strategy": "test",
                "questions": [
                    {
                        "id": "onset",
                        "question": "از چه زمانی؟",
                        "priority": 1,
                        "red_flag_related": False,
                    }
                ],
            }

        monkeypatch.setattr(llm_cascade, "_try_tier1_json", fake_tier1)

        result = await llm_cascade.generate_json_with_cascade(
            system_prompt="sys",
            user_prompt="user",
            tier3_factory=lambda: {"question_strategy": "fallback", "questions": []},
        )

        assert result.tier_used == 1
        assert result.llm_fallback_used is False
        validated = HPIQuestionsResponse.model_validate(result.data)
        assert validated.questions[0].id == "onset"

    @pytest.mark.asyncio
    async def test_tier1_fail_tier2_success(self, monkeypatch):
        async def fake_tier1(*_args, **_kwargs):
            raise OpenRouterServiceError("tier1 down")

        async def fake_tier2(*_args, **_kwargs):
            return {
                "question_strategy": "tier2",
                "questions": [
                    {
                        "id": "severity",
                        "question": "شدت؟",
                        "priority": 1,
                        "red_flag_related": False,
                    }
                ],
            }

        monkeypatch.setattr(llm_cascade, "_try_tier1_json", fake_tier1)
        monkeypatch.setattr(llm_cascade, "_try_tier2_json", fake_tier2)

        result = await llm_cascade.generate_json_with_cascade(
            system_prompt="sys",
            user_prompt="user",
            tier3_factory=lambda: {"question_strategy": "fallback", "questions": []},
        )

        assert result.tier_used == 2
        assert result.llm_fallback_used is True
        assert result.error_message is not None
        HPIQuestionsResponse.model_validate(result.data)

    @pytest.mark.asyncio
    async def test_tier1_and_tier2_fail_use_tier3(self, monkeypatch):
        async def fake_tier1(*_args, **_kwargs):
            raise OpenRouterServiceError("tier1 down")

        async def fake_tier2(*_args, **_kwargs):
            raise ValueError("bad json")

        monkeypatch.setattr(llm_cascade, "_try_tier1_json", fake_tier1)
        monkeypatch.setattr(llm_cascade, "_try_tier2_json", fake_tier2)

        tier3_data = {
            "question_strategy": "static",
            "questions": [
                {
                    "id": "location",
                    "question": "محل دقیق علامت کجاست؟",
                    "priority": 1,
                    "red_flag_related": False,
                }
            ],
        }

        result = await llm_cascade.generate_json_with_cascade(
            system_prompt="sys",
            user_prompt="user",
            tier3_factory=lambda: tier3_data,
        )

        assert result.tier_used == 3
        assert result.llm_fallback_used is True
        assert result.data == tier3_data
        HPIQuestionsResponse.model_validate(result.data)

    @pytest.mark.asyncio
    async def test_circuit_open_skips_tier1(self, monkeypatch):
        from app.services.llm_circuit_breaker import tier1_circuit_breaker

        tier1_called = False

        async def fake_tier1(*_args, **_kwargs):
            nonlocal tier1_called
            tier1_called = True
            return {"question_strategy": "x", "questions": []}

        async def fake_tier2(*_args, **_kwargs):
            return {
                "question_strategy": "tier2",
                "questions": [
                    {
                        "id": "a",
                        "question": "q",
                        "priority": 1,
                        "red_flag_related": False,
                    }
                ],
            }

        for _ in range(3):
            await tier1_circuit_breaker.record_tier1_failure(Exception("fail"))

        monkeypatch.setattr(llm_cascade, "_try_tier1_json", fake_tier1)
        monkeypatch.setattr(llm_cascade, "_try_tier2_json", fake_tier2)

        result = await llm_cascade.generate_json_with_cascade(
            system_prompt="sys",
            user_prompt="user",
            tier3_factory=lambda: {"question_strategy": "fallback", "questions": []},
        )

        assert tier1_called is False
        assert result.tier_used == 2

    @pytest.mark.asyncio
    async def test_malformed_json_escalates_to_tier3(self, monkeypatch):
        async def fake_tier1(*_args, **_kwargs):
            raise ValueError("Failed to parse JSON")

        async def fake_tier2(*_args, **_kwargs):
            raise ValueError("Failed to parse JSON")

        monkeypatch.setattr(llm_cascade, "_try_tier1_json", fake_tier1)
        monkeypatch.setattr(llm_cascade, "_try_tier2_json", fake_tier2)

        tier3_data = {
            "question_strategy": "static",
            "questions": [
                {
                    "id": "onset",
                    "question": "شروع؟",
                    "priority": 1,
                    "red_flag_related": False,
                }
            ],
        }

        result = await llm_cascade.generate_json_with_cascade(
            system_prompt="sys",
            user_prompt="user",
            tier3_factory=lambda: tier3_data,
        )

        assert result.tier_used == 3
        HPIQuestionsResponse.model_validate(result.data)

    @pytest.mark.asyncio
    async def test_chat_cascade_tier3_fallback(self, monkeypatch):
        async def fake_tier1(*_args, **_kwargs):
            raise OpenRouterServiceError("down")

        async def fake_tier2(*_args, **_kwargs):
            raise OpenRouterServiceError("down")

        monkeypatch.setattr(llm_cascade, "_try_tier1_chat", fake_tier1)
        monkeypatch.setattr(llm_cascade, "_try_tier2_chat", fake_tier2)

        result = await llm_cascade.chat_with_cascade(
            [{"role": "user", "content": "سلام"}],
            "system",
            tier3_factory=lambda: "سوال جایگزین",
        )

        assert result.tier_used == 3
        assert result.data == "سوال جایگزین"
        assert result.llm_fallback_used is True
