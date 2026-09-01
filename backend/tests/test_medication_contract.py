"""Medication contract tests: catalog, resolver, persistence, prescription split."""

from __future__ import annotations

from app.modules.medications.application.resolver import MedicationResolver
from app.modules.medications.domain.models import (
    Medication,
    MedicationCatalogSnapshot,
    MedicationPrescription,
    MedicationProvenance,
    MedicationSource,
    ResolvedMedication,
)
from app.modules.medications.infrastructure.catalog import (
    DarooyabCatalog,
    configured_catalog_path,
)
from app.schemas.intake import CurrentMedication, MedicalOverview
from app.schemas.clinical_context import ClinicalContext, MedicationEvidence
from app.schemas.medical import MedicalSummary
from app.services.medical_overview_service import overview_for_storage
from app.modules.workspace.application.projections.adapters import (
    ClinicalContentAdapters,
    DemographicsAdapter,
    DocumentAdapterItem,
    SessionAdapter,
    SoapAdapter,
)
from app.modules.workspace.application.projections.project_clinical_content import (
    project_clinical_content,
)


# ---------------------------------------------------------------- catalog

def test_runtime_catalog_is_deterministic_and_read_only() -> None:
    path = configured_catalog_path()
    assert path.name == "darooyab.db"
    assert str(path).endswith("backend/data/darooyab.db")
    assert path.is_file(), "runtime catalog missing; production image needs backend/data/darooyab.db"

    catalog = DarooyabCatalog()
    connection = catalog._connection()
    try:
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert {"drugs", "companies", "scrape_runs"} <= tables
        drugs, companies = connection.execute(
            "SELECT (SELECT COUNT(*) FROM drugs), (SELECT COUNT(*) FROM companies)"
        ).fetchone()
    finally:
        connection.close()

    assert drugs == 17960
    assert companies == 1514


def test_catalog_search_returns_canonical_catalog_fields() -> None:
    catalog = DarooyabCatalog()
    results = catalog.search("metformin", limit=5)
    assert results
    medication = results[0]
    assert medication.id
    assert medication.brand_name_en or medication.brand_name_fa
    assert medication.generic_name_en
    assert medication.company_slug

    snapshot = MedicationCatalogSnapshot.from_catalog(medication)
    assert snapshot.catalog_id == medication.id
    assert snapshot.generic_name == medication.generic_name_en
    assert snapshot.strength_raw == medication.strength
    assert snapshot.dosage_form == medication.form
    assert snapshot.company_slug == medication.company_slug


# --------------------------------------------------------------- resolver

def test_manual_and_ocr_resolution_produce_the_same_canonical_structure() -> None:
    resolver = MedicationResolver()
    manual = resolver.resolve_manual("metformin", limit=1)
    ocr = resolver.resolve_ocr("metformin", limit=1)

    assert manual.medications and ocr.medications
    manual_med = manual.medications[0]
    ocr_med = ocr.medications[0]
    assert isinstance(manual_med, ResolvedMedication)
    assert isinstance(ocr_med, ResolvedMedication)
    assert manual_med.catalog is not None
    assert manual_med.catalog == ocr_med.catalog
    assert manual_med.model_dump() == ocr_med.model_dump()


def test_composed_medication_keeps_catalog_and_prescription_separate() -> None:
    resolver = MedicationResolver()
    resolved = resolver.resolve_manual("metformin", limit=1).medications[0]
    composed = Medication.from_resolved(
        resolved,
        prescription=MedicationPrescription(
            dose="۱",
            dose_unit=resolved.dose_unit,
            frequency="روزی ۱ بار",
        ),
        provenance=MedicationProvenance(source=MedicationSource.MANUAL),
    )

    assert composed.catalog is not None
    assert composed.prescription is not None
    assert composed.catalog.strength_raw == resolved.strength
    assert composed.catalog.dosage_form == resolved.form
    # Prescription fields must never leak catalog values.
    assert composed.prescription.quantity is None
    assert composed.prescription.duration is None
    assert composed.prescription.route is None
    assert composed.prescription.instructions is None
    assert composed.prescription.dose == "۱"
    assert composed.provenance is not None
    assert composed.provenance.source == "manual"
    assert composed.provenance.verification_status == "unverified"


# ------------------------------------------------------------ persistence

def _catalog_medication() -> CurrentMedication:
    resolver = MedicationResolver()
    resolved = resolver.resolve_manual("metformin", limit=1).medications[0]
    composed = Medication.from_resolved(
        resolved,
        prescription=MedicationPrescription(
            dose="۱",
            dose_unit=resolved.dose_unit,
            frequency="روزی ۱ بار",
        ),
    )
    payload = composed.model_dump()
    return CurrentMedication(
        id="med-1",
        **payload,
    )


def test_catalog_information_survives_storage_round_trip() -> None:
    medication = _catalog_medication()
    overview = MedicalOverview(current_medications=[medication])

    stored = overview_for_storage(overview)
    stored_med = stored["current_medications"][0]
    assert stored_med["catalog"] is not None
    assert stored_med["prescription"] is not None

    reloaded = MedicalOverview.model_validate(stored)
    reloaded_med = reloaded.current_medications[0]
    assert reloaded_med.catalog is not None
    assert reloaded_med.catalog.catalog_id == medication.catalog_id
    assert reloaded_med.catalog.generic_name == medication.catalog.generic_name
    assert reloaded_med.catalog.brand_name == medication.catalog.brand_name
    assert reloaded_med.catalog.strength_raw == medication.catalog.strength_raw
    assert reloaded_med.catalog.dosage_form == medication.catalog.dosage_form
    assert reloaded_med.catalog.manufacturer == medication.catalog.manufacturer
    assert reloaded_med.catalog.company_name == medication.catalog.company_name
    assert reloaded_med.prescription is not None
    assert reloaded_med.prescription.frequency == "روزی ۱ بار"
    assert reloaded_med.provenance is not None


def test_medication_evidence_retains_catalog_and_prescription() -> None:
    medication = _catalog_medication()
    evidence = MedicationEvidence(
        medication_id=medication.id,
        catalog_id=medication.catalog_id,
        name=medication.name,
        amount=medication.amount,
        frequency=medication.frequency,
        dose_unit=medication.dose_unit,
        catalog=medication.catalog,
        prescription=medication.prescription,
        provenance=medication.provenance,
    )
    assert evidence.catalog == medication.catalog
    assert evidence.prescription == medication.prescription
    assert evidence.provenance == medication.provenance


# ------------------------------------------------------ backward compat

def test_legacy_medication_payload_still_deserializes() -> None:
    legacy = {
        "id": "med-legacy",
        "catalog_id": 101,
        "name": "Glucophage",
        "amount": "۱ قرص",
        "frequency": "روزی ۱ بار",
        "dose_unit": "قرص",
    }
    overview = MedicalOverview.model_validate(
        {"current_medications": [legacy]}
    )
    medication = overview.current_medications[0]
    assert medication.id == "med-legacy"
    assert medication.catalog_id == 101
    assert medication.name == "Glucophage"
    assert medication.amount == "۱ قرص"
    assert medication.catalog is None
    assert medication.prescription is None
    assert medication.provenance is None


def test_legacy_storage_payload_shape_is_preserved_when_fields_absent() -> None:
    overview = MedicalOverview(
        current_medications=[
            CurrentMedication(
                id="med-2",
                catalog_id=101,
                name="Glucophage",
                amount="۱ قرص",
                frequency="روزی ۱ بار",
                dose_unit="قرص",
            )
        ]
    )
    stored = overview_for_storage(overview)
    assert stored["current_medications"] == [
        {
            "id": "med-2",
            "catalog_id": 101,
            "name": "Glucophage",
            "amount": "۱ قرص",
            "frequency": "روزی ۱ بار",
            "dose_unit": "قرص",
        }
    ]


# ---------------------------------------------------------- workspace DTO

def test_workspace_projection_exposes_structured_medication_contract() -> None:
    medication = _catalog_medication()
    context = ClinicalContext(
        session_id=1,
        patient_id=7,
        summary=MedicalSummary(
            chief_complaint="Follow-up",
            current_medications=[],
            is_hpi_complete=True,
        ),
        medication_evidence=(
            MedicationEvidence(
                medication_id=medication.id,
                catalog_id=medication.catalog_id,
                name=medication.name,
                amount=medication.amount,
                frequency=medication.frequency,
                dose_unit=medication.dose_unit,
                catalog=medication.catalog,
                prescription=medication.prescription,
                provenance=medication.provenance,
            ),
        ),
    )
    adapters = ClinicalContentAdapters(
        session=SessionAdapter(
            session_id=1,
            status="active",
            visit_type="Follow-up",
            generated_at="2026-07-28T15:00:00+00:00",
        ),
        demographics=DemographicsAdapter(
            first_name="Jane",
            last_name="Doe",
            age=54,
            sex="female",
            national_id="MRN-10042",
        ),
        documents=(),
        soap=SoapAdapter(soap_note="", soap_status="ready"),
    )

    content = project_clinical_content(context, adapters).content
    assert content.medications is not None
    item = content.medications.groups[0].items[0]
    assert item.catalog_id == medication.catalog_id
    assert item.generic_name == medication.catalog.generic_name
    assert item.brand_name == medication.catalog.brand_name
    assert item.strength == medication.catalog.strength_raw
    assert item.dosage_form == medication.catalog.dosage_form
    assert item.manufacturer == medication.catalog.manufacturer
    assert item.company == medication.catalog.company_name
    assert item.dose == medication.prescription.dose
    assert item.dose_unit == medication.prescription.dose_unit
    assert item.frequency == medication.prescription.frequency
    assert item.source == "clinical_context"
    assert item.quantity is None
    assert item.duration is None
    assert item.route is None
    assert item.instructions is None
    assert item.verification_status == "unverified"
