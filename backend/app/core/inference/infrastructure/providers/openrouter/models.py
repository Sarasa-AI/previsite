"""OpenRouter provider-local wire models — must not import domain models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class OpenRouterMessage(BaseModel):
    """Single message in the conversation."""

    model_config = ConfigDict(frozen=True)

    role: str
    content: str


class OpenRouterProviderFinding(BaseModel):
    """Provider-level finding structure matching the model output schema."""

    model_config = ConfigDict(frozen=True)

    finding_key: str
    artifact_type: str
    title: str
    summary: str
    confidence: float | None = None
    attributes: dict[str, object] = Field(default_factory=dict)


class OpenRouterStructuredOutput(BaseModel):
    """Provider structured output — validated model JSON response.

    ``findings`` is REQUIRED. A reply that omits or misspells it is a schema
    violation, not "no findings": defaulting to an empty tuple would let a
    malformed provider response reach the domain as a silently-empty result.
    An explicit ``{"findings": []}`` is the only way to express "nothing found".
    """

    model_config = ConfigDict(frozen=True)

    findings: tuple[OpenRouterProviderFinding, ...]


class OpenRouterChoiceMessage(BaseModel):
    """Message object within a choice."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    role: str
    content: str | None = None


class OpenRouterChoice(BaseModel):
    """Single completion choice."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    index: int
    message: OpenRouterChoiceMessage
    finish_reason: str | None = None


class OpenRouterUsage(BaseModel):
    """Token usage statistics."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class OpenRouterCompletionResponse(BaseModel):
    """OpenRouter chat completion API response."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    id: str
    object: str
    created: int
    model: str
    choices: tuple[OpenRouterChoice, ...]
    usage: OpenRouterUsage | None = None
