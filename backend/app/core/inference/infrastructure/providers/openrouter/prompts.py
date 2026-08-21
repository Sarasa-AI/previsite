"""OpenRouter prompt construction — generic inference, no clinical logic."""

from __future__ import annotations

import json

from app.core.inference.infrastructure.providers.openrouter.models import (
    OpenRouterMessage,
)

# System instruction for generic structured inference
_SYSTEM_PROMPT = """You are a structured clinical inference assistant.

You will receive a clinical context reference containing structured extraction data from medical documents.
Your task is to analyze the extracted clinical values and produce structured findings.

The context_reference will be a JSON object with this structure:
{
  "type": "extraction_artifact",
  "artifact_id": 123,
  "file_id": 456,
  "session_id": 789,
  "extraction_summary": [
    {"name": "Hemoglobin", "value": "13.7", "unit": "g/dL", "abnormal": false, "needs_review": false, ...},
    {"name": "WBC", "value": "8,421", "unit": "/µL", "abnormal": false, "needs_review": false, ...}
  ]
}

Output JSON schema:
{
  "findings": [
    {
      "finding_key": "stable_unique_key",
      "artifact_type": "clinical_finding",
      "title": "Short descriptive title",
      "summary": "Concise summary with clinical interpretation",
      "confidence": 0.95,
      "attributes": {
        "category": "observation",
        "severity": "low",
        "source_values": ["Hemoglobin: 13.7 g/dL", "WBC: 8,421 /µL"]
      }
    }
  ]
}

Rules:
- Return ONLY valid JSON matching the schema above
- Do NOT wrap JSON in markdown code fences
- finding_key must be stable and unique (suggest: derive from session_id + analyte)
- artifact_type should be "clinical_finding" for lab value interpretations
- confidence must be between 0.0 and 1.0, or null if unknown
- If no clinically relevant findings can be extracted, return {"findings": []}
- Do NOT fabricate information not present in the extraction_summary
- Do NOT add explanatory text outside the JSON structure
- Focus on clinical interpretation: normal/abnormal, trends, clinical significance
- Map artifact attributes: category (red_flag/conflict/risk/observation/missing_data), severity (critical/high/moderate/low)"""


def build_inference_messages(
    context_reference: str,
    product_key: str,
) -> tuple[OpenRouterMessage, ...]:
    """Build provider-local messages for an inference request.

    Parameters
    ----------
    context_reference : str
        Opaque reference to the clinical context (JSON string with extraction data).
    product_key : str
        Product identifier for potential future routing/logging.

    Returns
    -------
    tuple[OpenRouterMessage, ...]
        Message sequence for the OpenRouter completion request.

    Notes
    -----
    The context_reference is parsed as JSON to extract the extraction_summary.
    If parsing fails, the raw string is included as a fallback.
    """
    # Try to parse the context reference as JSON
    extraction_summary = []
    try:
        context_data = json.loads(context_reference)
        if isinstance(context_data, dict):
            extraction_summary = context_data.get("extraction_summary", [])
    except (json.JSONDecodeError, TypeError):
        # If not valid JSON, include as raw text
        extraction_summary = [{"raw_text": context_reference}]

    # Build user content with the extraction data
    if extraction_summary:
        # Format extraction values for the prompt
        formatted_values = []
        for item in extraction_summary:
            if isinstance(item, dict):
                name = item.get("name", "Unknown")
                value = item.get("value", "")
                unit = item.get("unit", "")
                abnormal = item.get("abnormal", False)
                needs_review = item.get("needs_review", False)
                line = f"- {name}: {value} {unit}".strip()
                if abnormal:
                    line += " (ABNORMAL)"
                if needs_review:
                    line += " (NEEDS REVIEW)"
                formatted_values.append(line)
            else:
                formatted_values.append(f"- {item}")

        user_content = (
            f"Product: {product_key}\n\n"
            f"Extracted clinical values from medical document:\n"
            f"{chr(10).join(formatted_values)}\n\n"
            f"Analyze these values and produce structured clinical findings. "
            f"Focus on: abnormal values, clinical significance, potential risks, "
            f"and any values requiring clinical review."
        )
    else:
        user_content = (
            f"Context reference: {context_reference}\n"
            f"Product: {product_key}\n\n"
            f"Extract structured findings from the above context reference."
        )

    return (
        OpenRouterMessage(role="system", content=_SYSTEM_PROMPT),
        OpenRouterMessage(role="user", content=user_content),
    )
