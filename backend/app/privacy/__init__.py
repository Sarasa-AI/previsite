"""Privacy / consent helpers (structure only — no legal copy)."""

from app.privacy.consent_keys import (
    AI_PROCESSING,
    ALL_CONSENT_KEYS,
    CONSENT_REQUIRED_CODE,
    DATA_PROCESSING,
    ENFORCEMENT_REQUIRED_KEYS,
    EXTERNAL_LLM_PROCESSING,
    RECORDING,
    current_version_for,
)
from app.privacy.consent_service import (
    get_consent_status,
    grant_consent,
    list_consent_records,
    missing_required_consents,
    require_patient_consents,
    withdraw_consent,
)

__all__ = [
    "AI_PROCESSING",
    "ALL_CONSENT_KEYS",
    "CONSENT_REQUIRED_CODE",
    "DATA_PROCESSING",
    "ENFORCEMENT_REQUIRED_KEYS",
    "EXTERNAL_LLM_PROCESSING",
    "RECORDING",
    "current_version_for",
    "get_consent_status",
    "grant_consent",
    "list_consent_records",
    "missing_required_consents",
    "require_patient_consents",
    "withdraw_consent",
]
