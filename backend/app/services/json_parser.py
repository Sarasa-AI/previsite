import json
import re
import logging

logger = logging.getLogger(__name__)


def parse_llm_json(text: str) -> dict:
    """Extract and parse JSON from an LLM response with strict validation."""
    if not text or not text.strip():
        raise ValueError("Empty LLM response")

    cleaned = text.strip()

    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    if fence_match:
        cleaned = fence_match.group(1).strip()

    brace_start = cleaned.find("{")
    brace_end = cleaned.rfind("}")
    if brace_start == -1 or brace_end == -1 or brace_end <= brace_start:
        raise ValueError("No JSON object found in LLM response")

    json_str = cleaned[brace_start : brace_end + 1]

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as exc:
        logger.error("JSON parse failed: %s | raw=%s", exc, json_str[:500])
        raise ValueError(f"Invalid JSON in LLM response: {exc}") from exc
