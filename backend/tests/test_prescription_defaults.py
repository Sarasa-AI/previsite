"""Prescription defaults must stay truthful, never look like extracted instructions."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.medications.domain.models import (
    CatalogMedication,
    Medication,
    MedicationPrescription,
    MedicationProvenance,
    MedicationSource,
)
from app.modules.medications.application.resolver import MedicationResolver
from app.services.ocr_service import (
    _extract_prescription_instructions,
    _medication_ocr_item,
    _strip_prescription_phrases,
)
from app.schemas.intake import CurrentMedication, MedicalOverview
from app.services.clinical_context_builder import _derive_medication_evidence
from app.services.medical_overview_service import overview_for_storage


def test_typed_unknown_prescription_keeps_null_and_does_not_fabricate_dose() -> None:
    resolver = MedicationResolver()
    resolved = resolver.resolve_manual("metformin", limit=1).medications[0]
    composed = Medication.from_resolved(
        resolved,
        provenance=MedicationProvenance(source=MedicationSource.MANUAL),
    )

    assert composed.prescription is not None
    assert composed.prescription.dose is None
    assert composed.prescription.frequency is None
    assert composed.amount == ""          # legacy mirror stays empty when unknown
    assert composed.frequency == ""
    assert composed.provenance is not None
    assert composed.provenance.source == "manual"
    assert composed.provenance.verification_status == "unverified"


def test_ocr_output_keeps_unknown_prescription_fields_null() -> None:
    resolver = MedicationResolver()
    resolved = resolver.resolve_manual("metformin", limit=1).medications[0]
    item = _medication_ocr_item(resolved)

    assert item["amount"] == ""
    assert item["frequency"] == ""
    prescription = item["prescription"]
    assert isinstance(prescription, dict)
    assert prescription["dose"] is None
    assert prescription["quantity"] is None
    assert prescription["frequency"] is None
    assert prescription["duration"] is None
    assert prescription["route"] is None
    assert prescription["instructions"] is None
    assert prescription["dose_unit"] is not None  # form-inferred unit only
    assert item["provenance"]["verification_status"] == "needs_review"


def test_ocr_frequency_default_is_not_exposed_as_instruction() -> None:
    resolver = MedicationResolver()
    resolved = resolver.resolve_manual("metformin", limit=1).medications[0]
    payload = _medication_ocr_item(resolved)
    assert "روزی ۱ بار" not in payload["frequency"]
    assert payload["catalog"]["strength_raw"] != payload["prescription"]["dose"]


def test_ocr_never_infers_quantity_or_route() -> None:
    # Package/quantity-looking text must not become prescription data.
    extracted = _extract_prescription_instructions("آموکسی سیلین ۶۰ قرص")
    assert extracted == {}

    # Strength is not dose.
    extracted = _extract_prescription_instructions("Metformin 500 mg")
    assert extracted == {}


def test_ocr_extracts_explicit_frequency_and_instructions_only() -> None:
    extracted = _extract_prescription_instructions("لوزارتان روزی دو بار بعد از غذا")
    assert extracted["frequency"] == "روزی ۲ بار"
    assert extracted["instructions"] == "بعد از غذا"
    assert "dose" not in extracted
    assert _strip_prescription_phrases("لوزارتان روزی دو بار بعد از غذا") == "لوزارتان"


def test_ocr_extracts_explicit_dose_phrase() -> None:
    extracted = _extract_prescription_instructions("متفورمین یک قرص صبح و شب")
    assert extracted["dose"] == "۱"
    assert extracted["dose_unit"] == "قرص"
    assert _strip_prescription_phrases("متفورمین یک قرص صبح و شب") == "متفورمین"


def test_ambiguous_ocr_candidates_are_exposed_and_never_confirmed() -> None:
    resolver = MedicationResolver()
    resolution = resolver.resolve_manual("متفورمین", limit=2)
    assert len(resolution.medications) >= 2
    item = _medication_ocr_item(
        resolution.medications[0],
        candidates=(resolution.medications[0], resolution.medications[1]),
    )
    assert item["ambiguous"] is True
    assert item["candidate_count"] == 2
    assert item["provenance"]["verification_status"] == "ambiguous"
    assert len(item["candidates"]) == 2


def test_prescription_validation_rejects_negative_values() -> None:
    with pytest.raises(ValidationError):
        MedicationPrescription(quantity="-5")
    with pytest.raises(ValidationError):
        MedicationPrescription(duration="-1 روز")
    with pytest.raises(ValidationError):
        MedicationPrescription(quantity="-۳")


def test_prescription_validation_accepts_textual_values() -> None:
    prescription = MedicationPrescription(
        dose="۱",
        dose_unit="قرص",
        quantity="1 bottle",
        duration="30 days",
        route="oral",
        instructions="بعد از غذا",
    )
    assert prescription.quantity == "1 bottle"


def test_catalog_strength_is_never_treated_as_prescription_dose() -> None:
    resolver = MedicationResolver()
    resolved = resolver.resolve_manual("metformin 500", limit=1).medications[0]
    composed = Medication.from_resolved(
        resolved,
        prescription=MedicationPrescription(dose="۱", dose_unit=resolved.dose_unit),
    )
    assert composed.catalog is not None
    assert composed.catalog.strength_raw != composed.prescription.dose
    assert composed.prescription.quantity is None


def test_full_prescription_survives_storage_evidence_and_flat_mirrors() -> None:
    resolver = MedicationResolver()
    resolved = resolver.resolve_manual("متفورمین ۵۰۰", limit=1).medications[0]
    composed = Medication.from_resolved(
        resolved,
        prescription=MedicationPrescription(
            dose="۱",
            dose_unit="قرص",
            quantity="۳۰",
            frequency="روزی ۲ بار",
            duration="۳۰ روز",
            route="خوراکی",
            instructions="بعد از غذا",
        ),
        provenance=MedicationProvenance(
            source=MedicationSource.MANUAL,
            verification_status="confirmed",
        ),
    )

    overview = MedicalOverview(
        current_medications=[
            CurrentMedication(id="m1", **composed.model_dump())
        ]
    )
    stored = overview_for_storage(overview)
    reloaded = MedicalOverview.model_validate(stored)

    evidence_list, analyses = _derive_medication_evidence(reloaded)
    assert len(evidence_list) == 1
    evidence = evidence_list[0]
    assert evidence.catalog is not None
    assert evidence.catalog.catalog_id == resolved.id
    assert evidence.catalog.generic_name == resolved.generic_name_en
    assert evidence.catalog.strength_raw == resolved.strength
    assert evidence.catalog.dosage_form == resolved.form
    assert evidence.catalog.manufacturer == resolved.manufacturer
    assert evidence.prescription is not None
    assert evidence.prescription.dose == "۱"
    assert evidence.prescription.dose_unit == "قرص"
    assert evidence.prescription.quantity == "۳۰"
    assert evidence.prescription.frequency == "روزی ۲ بار"
    assert evidence.prescription.duration == "۳۰ روز"
    assert evidence.prescription.route == "خوراکی"
    assert evidence.prescription.instructions == "بعد از غذا"
    # Legacy flat mirrors stay truthful: amount keeps the combined dose form.
    assert evidence.amount == "۱ قرص"
    assert evidence.frequency == "روزی ۲ بار"
    assert evidence.dose_unit == "قرص"
    assert evidence.provenance is not None
    assert evidence.provenance.verification_status == "confirmed"

    item = analyses[0].medications[0]
    assert item.dose == "۱"
    assert item.frequency == "روزی ۲ بار"
