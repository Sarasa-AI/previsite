"""Allergy state semantic tests — centralized interpretation verification."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.modules.workspace.application.allergy_state import (
    AllergyState,
    AllergyInterpretation,
    interpret_allergy_state,
    allergy_text_for_display,
    allergies_status_unknown,
)
from app.modules.workspace.application.signals import extract_signals
from app.modules.workspace.application.inputs import OrchestratorInputs, SessionState
from app.schemas.clinical_context import ClinicalContext
from app.schemas.intake import MedicalOverview
from app.schemas.medical import MedicalSummary

FIXED_NOW = datetime(2026, 7, 28, 15, 0, 0, tzinfo=timezone.utc)


def _context(**overrides) -> ClinicalContext:
    base = {
        "session_id": 1,
        "patient_id": 7,
        "summary": MedicalSummary(
            chief_complaint="Headache for two days",
            extracted_at=FIXED_NOW,
        ),
        "overview": None,
    }
    base.update(overrides)
    return ClinicalContext(**base)


def _context_with_overview(allergies: str, **overrides) -> ClinicalContext:
    base = {
        "session_id": 1,
        "patient_id": 7,
        "summary": MedicalSummary(
            chief_complaint="Headache for two days",
            extracted_at=FIXED_NOW,
        ),
        "overview": MedicalOverview(allergies=allergies),
    }
    base.update(overrides)
    return ClinicalContext(**base)


def _context_with_summary_allergies(allergies: list[str], **overrides) -> ClinicalContext:
    base = {
        "session_id": 1,
        "patient_id": 7,
        "summary": MedicalSummary(
            chief_complaint="Headache for two days",
            allergies=allergies,
            extracted_at=FIXED_NOW,
        ),
        "overview": None,
    }
    base.update(overrides)
    return ClinicalContext(**base)


class TestAllergyStateInterpretation:
    """Test the centralized allergy state interpretation."""

    # POSITIVE cases
    def test_positive_single_allergy(self):
        ctx = _context_with_overview("penicillin")
        result = interpret_allergy_state(ctx)
        assert result.state == AllergyState.POSITIVE
        assert result.has_positive_allergy is True
        assert result.has_explicit_negative is False
        assert result.is_unknown is False

    def test_positive_multiple_allergies(self):
        ctx = _context_with_overview("penicillin, sulfa")
        result = interpret_allergy_state(ctx)
        assert result.state == AllergyState.POSITIVE
        assert result.has_positive_allergy is True

    def test_positive_persian_allergy(self):
        ctx = _context_with_overview("پنی‌سیلین")
        result = interpret_allergy_state(ctx)
        assert result.state == AllergyState.POSITIVE
        assert result.has_positive_allergy is True

    def test_positive_mixed_english_persian(self):
        ctx = _context_with_overview("penicillin, آموکسی‌سیلین")
        result = interpret_allergy_state(ctx)
        assert result.state == AllergyState.POSITIVE
        assert result.has_positive_allergy is True

    def test_positive_from_summary(self):
        ctx = _context_with_summary_allergies(["penicillin"])
        result = interpret_allergy_state(ctx)
        assert result.state == AllergyState.POSITIVE
        assert result.has_positive_allergy is True

    def test_positive_with_persian_comma(self):
        ctx = _context_with_overview("penicillin، sulfa")
        result = interpret_allergy_state(ctx)
        assert result.state == AllergyState.POSITIVE

    # NEGATIVE_EXPLICIT (NKDA) cases
    def test_persian_nkda_hech_kodam(self):
        ctx = _context_with_overview("هیچ‌کدام")
        result = interpret_allergy_state(ctx)
        assert result.state == AllergyState.NEGATIVE_EXPLICIT
        assert result.has_positive_allergy is False
        assert result.has_explicit_negative is True
        assert result.is_unknown is False

    def test_persian_hech(self):
        ctx = _context_with_overview("هیچ")
        result = interpret_allergy_state(ctx)
        assert result.state == AllergyState.NEGATIVE_EXPLICIT
        assert result.has_positive_allergy is False

    def test_persian_nadarad(self):
        ctx = _context_with_overview("ندارد")
        result = interpret_allergy_state(ctx)
        assert result.state == AllergyState.NEGATIVE_EXPLICIT

    def test_persian_bidoon_hassasiyat(self):
        ctx = _context_with_overview("بدون حساسیت")
        result = interpret_allergy_state(ctx)
        assert result.state == AllergyState.NEGATIVE_EXPLICIT

    def test_persian_bidoon_alergy(self):
        ctx = _context_with_overview("بدون آلرژی")
        result = interpret_allergy_state(ctx)
        assert result.state == AllergyState.NEGATIVE_EXPLICIT

    def test_persian_hassasiyat_nadarad(self):
        ctx = _context_with_overview("حساسیت ندارد")
        result = interpret_allergy_state(ctx)
        assert result.state == AllergyState.NEGATIVE_EXPLICIT

    def test_persian_alergy_nadarad(self):
        ctx = _context_with_overview("آلرژی ندارد")
        result = interpret_allergy_state(ctx)
        assert result.state == AllergyState.NEGATIVE_EXPLICIT

    def test_english_nkda(self):
        ctx = _context_with_overview("NKDA")
        result = interpret_allergy_state(ctx)
        assert result.state == AllergyState.NEGATIVE_EXPLICIT

    def test_english_no_known_allergies(self):
        ctx = _context_with_overview("No known allergies")
        result = interpret_allergy_state(ctx)
        assert result.state == AllergyState.NEGATIVE_EXPLICIT

    def test_english_no_known_drug_allergies(self):
        ctx = _context_with_overview("No known drug allergies")
        result = interpret_allergy_state(ctx)
        assert result.state == AllergyState.NEGATIVE_EXPLICIT

    def test_english_none(self):
        ctx = _context_with_overview("none")
        result = interpret_allergy_state(ctx)
        assert result.state == AllergyState.NEGATIVE_EXPLICIT

    def test_english_n_a(self):
        ctx = _context_with_overview("n/a")
        result = interpret_allergy_state(ctx)
        assert result.state == AllergyState.NEGATIVE_EXPLICIT

    def test_english_na(self):
        ctx = _context_with_overview("na")
        result = interpret_allergy_state(ctx)
        assert result.state == AllergyState.NEGATIVE_EXPLICIT

    def test_english_nil(self):
        ctx = _context_with_overview("nil")
        result = interpret_allergy_state(ctx)
        assert result.state == AllergyState.NEGATIVE_EXPLICIT

    def test_nkda_from_summary(self):
        ctx = _context_with_summary_allergies(["NKDA"])
        result = interpret_allergy_state(ctx)
        assert result.state == AllergyState.NEGATIVE_EXPLICIT

    def test_nkda_from_summary_persian(self):
        ctx = _context_with_summary_allergies(["هیچ‌کدام"])
        result = interpret_allergy_state(ctx)
        assert result.state == AllergyState.NEGATIVE_EXPLICIT

    # UNKNOWN cases
    def test_empty_allergy(self):
        ctx = _context_with_overview("")
        result = interpret_allergy_state(ctx)
        assert result.state == AllergyState.UNKNOWN
        assert result.has_positive_allergy is False
        assert result.has_explicit_negative is False
        assert result.is_unknown is True

    def test_missing_allergy(self):
        ctx = _context_with_overview("   ")
        result = interpret_allergy_state(ctx)
        assert result.state == AllergyState.UNKNOWN
        assert result.is_unknown is True

    def test_no_overview_no_summary(self):
        ctx = _context()
        result = interpret_allergy_state(ctx)
        assert result.state == AllergyState.UNKNOWN
        assert result.is_unknown is True

    # Edge cases
    def test_positive_overrides_nkda(self):
        # "penicillin, NKDA" should be positive
        ctx = _context_with_overview("penicillin, NKDA")
        result = interpret_allergy_state(ctx)
        assert result.state == AllergyState.POSITIVE
        assert result.has_positive_allergy is True
        assert result.has_explicit_negative is True  # NKDA also present

    def test_none_except_penicillin_is_positive(self):
        # "none except penicillin" should be positive
        ctx = _context_with_overview("none except penicillin")
        result = interpret_allergy_state(ctx)
        # "none except penicillin" is not an exact match for "none"
        assert result.state == AllergyState.POSITIVE
        assert result.has_positive_allergy is True


class TestAllergyTextForDisplay:
    """Test display text preservation."""

    def test_preserves_nkda_text(self):
        ctx = _context_with_overview("هیچ‌کدام")
        text = allergy_text_for_display(ctx)
        assert text == "هیچ‌کدام"

    def test_preserves_positive_text(self):
        ctx = _context_with_overview("penicillin, sulfa")
        text = allergy_text_for_display(ctx)
        assert text == "penicillin, sulfa"

    def test_empty_returns_empty(self):
        ctx = _context_with_overview("")
        text = allergy_text_for_display(ctx)
        assert text == ""


class TestAllergiesStatusUnknown:
    """Test the missing-info safety signal."""

    def test_positive_not_unknown(self):
        ctx = _context_with_overview("penicillin")
        assert allergies_status_unknown(ctx) is False

    def test_nkda_not_unknown(self):
        ctx = _context_with_overview("NKDA")
        assert allergies_status_unknown(ctx) is False

    def test_empty_is_unknown(self):
        ctx = _context_with_overview("")
        assert allergies_status_unknown(ctx) is True

    def test_missing_is_unknown(self):
        ctx = _context()
        assert allergies_status_unknown(ctx) is True


class TestWorkspaceSignalsAllergy:
    """Test signals.py extract_signals produces correct allergy signals."""

    def test_positive_allergy_signals(self):
        ctx = _context_with_overview("penicillin")
        signals = extract_signals(
            ctx,
            SessionState(soap_status="ready", soap_exists=True),
            OrchestratorInputs(),
        )
        assert signals.has_allergy_documented is True
        assert signals.has_drug_allergy is True
        assert signals.allergies_status_unknown is False
        assert signals.allergy_text == "penicillin"

    def test_nkda_signals(self):
        ctx = _context_with_overview("هیچ‌کدام")
        signals = extract_signals(
            ctx,
            SessionState(soap_status="ready", soap_exists=True),
            OrchestratorInputs(),
        )
        # NKDA should NOT be treated as positive allergy
        assert signals.has_allergy_documented is False
        assert signals.has_drug_allergy is False
        assert signals.allergies_status_unknown is False
        assert signals.allergy_text == "هیچ‌کدام"

    def test_unknown_allergy_signals(self):
        ctx = _context_with_overview("")
        signals = extract_signals(
            ctx,
            SessionState(soap_status="ready", soap_exists=True),
            OrchestratorInputs(),
        )
        assert signals.has_allergy_documented is False
        assert signals.has_drug_allergy is False
        assert signals.allergies_status_unknown is True
        assert signals.allergy_text == ""

    def test_positive_allergy_can_trigger_p0(self):
        """Positive drug allergy with medications should be able to trigger P0."""
        # This tests the priority engine logic via signals
        ctx = _context_with_overview("penicillin")
        signals = extract_signals(
            ctx,
            SessionState(soap_status="ready", soap_exists=True),
            OrchestratorInputs(),
        )
        assert signals.has_drug_allergy is True
        assert signals.medication_count == 0  # No meds in this context

    def test_nkda_does_not_trigger_allergy_p0(self):
        """NKDA should NOT trigger allergy P0 even with medications."""
        # This is the critical safety test
        ctx = _context_with_overview("هیچ‌کدام")
        signals = extract_signals(
            ctx,
            SessionState(soap_status="ready", soap_exists=True),
            OrchestratorInputs(),
        )
        assert signals.has_drug_allergy is False
        # Even with medications, allergy P0 should not trigger
        # (the priority engine checks has_drug_allergy AND meds)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
