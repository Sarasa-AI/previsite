"""Stable consent key identifiers and placeholder copy-text keys.

Do not invent medical or legal wording here — UI/copy resolves
``copy_text_key`` values later (e.g. ``consent.copy.ai_processing.v1``).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings

# Stable consent keys (never rename casually — stored in patient_consents).
AI_PROCESSING = "ai_processing"
DATA_PROCESSING = "data_processing"
RECORDING = "recording"
# Dormant in P2-B — defined for future use; NOT enforced. Do not add
# enforcement for external_llm_processing in this phase. Product-owner
# ai_processing wording must disclose third-party LLM providers.
EXTERNAL_LLM_PROCESSING = "external_llm_processing"

ALL_CONSENT_KEYS: tuple[str, ...] = (
    AI_PROCESSING,
    DATA_PROCESSING,
    RECORDING,
    EXTERNAL_LLM_PROCESSING,
)

# Required before session create / chat write / intake write when enforcement is on.
ENFORCEMENT_REQUIRED_KEYS: tuple[str, ...] = (
    AI_PROCESSING,
    DATA_PROCESSING,
)

CONSENT_REQUIRED_CODE = "CONSENT_REQUIRED"


@dataclass(frozen=True)
class ConsentKeySpec:
    key: str
    """Placeholder identifier for localized copy — not display text."""
    copy_text_key: str


def current_version_for(key: str) -> str:
    """Return the currently required policy version for a consent key."""
    mapping = {
        AI_PROCESSING: settings.consent_version_ai_processing,
        DATA_PROCESSING: settings.consent_version_data_processing,
        RECORDING: settings.consent_version_recording,
        EXTERNAL_LLM_PROCESSING: settings.consent_version_external_llm_processing,
    }
    if key not in mapping:
        raise KeyError(f"Unknown consent key: {key}")
    return mapping[key]


def copy_text_key_for(key: str, version: str | None = None) -> str:
    """Stable placeholder copy key, e.g. consent.copy.ai_processing.v1."""
    ver = version or current_version_for(key)
    return f"consent.copy.{key}.{ver}"


def all_consent_specs() -> list[ConsentKeySpec]:
    return [
        ConsentKeySpec(key=k, copy_text_key=copy_text_key_for(k))
        for k in ALL_CONSENT_KEYS
    ]


def is_known_consent_key(key: str) -> bool:
    return key in ALL_CONSENT_KEYS
