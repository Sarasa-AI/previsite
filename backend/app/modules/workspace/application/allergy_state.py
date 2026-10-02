"""Centralized allergy state interpretation — single source of clinical truth.

This module provides the authoritative interpretation of allergy data
from ClinicalContext into the three clinical semantic states:

    POSITIVE          — patient has a documented allergy
    NEGATIVE_EXPLICIT — patient explicitly has no known allergies (NKDA)
    UNKNOWN           — allergy status not assessed / missing

All downstream modules must derive allergy signals from this single source.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.schemas.clinical_context import ClinicalContext


class AllergyState(Enum):
    """Clinical semantic state of allergy information."""

    POSITIVE = "positive"
    NEGATIVE_EXPLICIT = "negative_explicit"
    UNKNOWN = "unknown"


# Canonical negation terms — includes both English and Persian clinical terms.
# These represent explicit patient/physician statements of NO allergy.
# Do NOT match substrings inside positive clinical statements.
_ALLERGY_NEGATIONS = frozenset(
    {
        # English
        "nkda",
        "no known allergies",
        "no known drug allergies",
        "no allergies",
        "none",
        "n/a",
        "na",
        "nil",
        "no known allergy",
        # Persian (with and without zero-width non-joiner)
        "هیچ‌کدام",
        "هیچکدام",
        "هیچ کدام",  # without ZWNJ
        "هیچ",
        "ندارد",
        "بدون حساسیت",
        "بدون آلرژی",
        "حساسیت ندارد",
        "آلرژی ندارد",
        "حساسیت نداره",
        "آلرژی نداره",
    }
)


def _normalize_allergy_item(item: str) -> str:
    """Normalize a single allergy item for comparison."""
    # Remove zero-width characters for comparison
    return item.strip().replace("\u200c", "").replace("\u200d", "").lower()


def _is_explicit_negation(text: str) -> bool:
    """Check if the entire text represents an explicit NKDA statement."""
    normalized = _normalize_allergy_item(text)
    return normalized in _ALLERGY_NEGATIONS


def _is_positive_allergy(text: str) -> bool:
    """Check if text represents a positive allergy (not empty, not NKDA)."""
    normalized = _normalize_allergy_item(text)
    if not normalized:
        return False
    if normalized in _ALLERGY_NEGATIONS:
        return False
    # Allow "none" as negation but not as part of a longer phrase
    # e.g., "none except penicillin" should be positive
    if normalized == "none":
        return False
    return True


@dataclass(frozen=True)
class AllergyInterpretation:
    """Complete allergy interpretation for a session."""

    state: AllergyState
    allergy_text: str  # Original/raw text for display
    has_positive_allergy: bool
    has_explicit_negative: bool
    is_unknown: bool


def interpret_allergy_state(context: ClinicalContext) -> AllergyInterpretation:
    """
    Interpret allergy state from ClinicalContext — single source of truth.

    Priority order:
    1. overview.allergies (structured, preferred)
    2. summary.allergies (legacy)
    3. empty/missing → UNKNOWN
    """
    # Get raw allergy text from preferred sources
    raw_text = ""

    if context.overview and (context.overview.allergies or "").strip():
        raw_text = context.overview.allergies.strip()
    elif context.summary.allergies:
        items = [str(a).strip() for a in context.summary.allergies if a and str(a).strip()]
        raw_text = ", ".join(items)

    # Normalize: split by comma/Persian comma and analyze each item
    items = [item.strip() for item in raw_text.replace("،", ",").split(",") if item.strip()]

    # Determine state
    positive_items = []
    negative_items = []

    for item in items:
        if _is_positive_allergy(item):
            positive_items.append(item)
        elif _is_explicit_negation(item):
            negative_items.append(item)

    if positive_items:
        # Any positive allergy dominates — even if NKDA also present
        # (e.g., "penicillin, NKDA" is clinically positive)
        return AllergyInterpretation(
            state=AllergyState.POSITIVE,
            allergy_text=raw_text,
            has_positive_allergy=True,
            has_explicit_negative=bool(negative_items),
            is_unknown=False,
        )

    if negative_items:
        # Explicit negative with no positives
        return AllergyInterpretation(
            state=AllergyState.NEGATIVE_EXPLICIT,
            allergy_text=raw_text,
            has_positive_allergy=False,
            has_explicit_negative=True,
            is_unknown=False,
        )

    # No allergy information at all
    return AllergyInterpretation(
        state=AllergyState.UNKNOWN,
        allergy_text="",
        has_positive_allergy=False,
        has_explicit_negative=False,
        is_unknown=True,
    )


def allergy_text_for_display(context: ClinicalContext) -> str:
    """Get allergy text suitable for UI display (preserves NKDA text)."""
    interp = interpret_allergy_state(context)
    return interp.allergy_text


def allergies_status_unknown(context: ClinicalContext) -> bool:
    """True when allergy status was never established (for missing-info safety)."""
    return interpret_allergy_state(context).is_unknown


__all__ = [
    "AllergyState",
    "AllergyInterpretation",
    "interpret_allergy_state",
    "allergy_text_for_display",
    "allergies_status_unknown",
]
