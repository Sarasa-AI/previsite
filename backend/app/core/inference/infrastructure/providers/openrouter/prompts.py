"""OpenRouter prompt construction — generic inference, no clinical logic."""

from __future__ import annotations

from app.core.inference.infrastructure.providers.openrouter.models import (
    OpenRouterMessage,
)

# System instruction for generic structured inference
_SYSTEM_PROMPT = """You are a structured inference assistant.

You will receive an opaque context reference and must return findings in strict JSON format.

Output JSON schema:
{
  "findings": [
    {
      "finding_key": "stable_unique_key",
      "artifact_type": "clinical_finding",
      "title": "Short descriptive title",
      "summary": "Concise summary",
      "confidence": 0.95,
      "attributes": {}
    }
  ]
}

Rules:
- Return ONLY valid JSON matching the schema above
- Do NOT wrap JSON in markdown code fences
- finding_key must be stable and unique
- artifact_type should be "clinical_finding" for generic findings
- confidence must be between 0.0 and 1.0, or null if unknown
- If no findings can be extracted, return {"findings": []}
- Do NOT fabricate information
- Do NOT add explanatory text outside the JSON structure"""


def build_inference_messages(
    context_reference: str,
    product_key: str,
) -> tuple[OpenRouterMessage, ...]:
    """Build provider-local messages for an inference request.

    Parameters
    ----------
    context_reference : str
        Opaque reference to the clinical context (not resolved in this layer).
    product_key : str
        Product identifier for potential future routing/logging.

    Returns
    -------
    tuple[OpenRouterMessage, ...]
        Message sequence for the OpenRouter completion request.

    Notes
    -----
    This implementation treats context_reference as opaque. Real clinical
    context resolution is outside the scope of this provider layer.
    """
    user_content = (
        f"Context reference: {context_reference}\n"
        f"Product: {product_key}\n\n"
        f"Extract structured findings from the above context reference."
    )

    return (
        OpenRouterMessage(role="system", content=_SYSTEM_PROMPT),
        OpenRouterMessage(role="user", content=user_content),
    )
