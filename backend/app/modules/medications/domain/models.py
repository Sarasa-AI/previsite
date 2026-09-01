"""Immutable medication domain models."""

from __future__ import annotations

from enum import Enum
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


_NUMERIC_SIGNED_RE = re.compile(r"[-+]?\d+(?:[.,٫]\d+)?")


def _parse_signed_number(value: str) -> float | None:
    """Return the first signed number in a string (Persian digits accepted)."""

    normalized = value.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")).replace("٫", ".")
    match = _NUMERIC_SIGNED_RE.search(normalized)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


class MedicationSource(str, Enum):
    """The workflow that supplied a medication query."""

    MANUAL = "manual"
    OCR = "ocr"


class CatalogMedication(BaseModel):
    """One medication row from the Darooyab catalog.

    ``strength`` is the raw DrugYab free-text strength and ``form`` is the
    DrugYab dosage-form code. Neither is normalized or interpreted here.
    """

    model_config = ConfigDict(frozen=True)

    id: int
    brand_name_fa: str | None = None
    brand_name_en: str | None = None
    generic_name_en: str | None = None
    form: str | None = None
    strength: str | None = None
    manufacturer: str | None = None
    brand_slug: str | None = None
    generic_slug: str | None = None
    company_slug: str | None = None
    company_name: str | None = None


class ResolvedMedication(CatalogMedication):
    """A catalog medication enriched with presentation rules."""

    display_name: str
    dose_unit: str
    catalog: MedicationCatalogSnapshot | None = None


class MedicationCatalogSnapshot(BaseModel):
    """Immutable snapshot of the DrugYab catalog facts for one product.

    This is captured at selection/resolution time and persisted with the
    patient's medication record so the historical record does not depend on a
    future DrugYab catalog refresh.

    ``strength_raw`` and ``dosage_form`` keep the DrugYab values verbatim:
    ``strength_raw`` is free text (e.g. ``10g/15ml/240ml``) and must never be
    interpreted as prescription dose.
    """

    model_config = ConfigDict(frozen=True)

    catalog_id: int | None = None
    brand_name: str | None = None
    brand_name_fa: str | None = None
    brand_name_en: str | None = None
    generic_name: str | None = None
    generic_name_en: str | None = None
    generic_slug: str | None = None
    brand_slug: str | None = None
    strength_raw: str | None = None
    dosage_form: str | None = None
    manufacturer: str | None = None
    company_name: str | None = None
    company_slug: str | None = None

    @classmethod
    def from_catalog(cls, medication: CatalogMedication) -> MedicationCatalogSnapshot:
        """Build a snapshot from a catalog row without inventing values."""

        return cls(
            catalog_id=medication.id,
            brand_name=medication.brand_name_en or medication.brand_name_fa,
            brand_name_fa=medication.brand_name_fa,
            brand_name_en=medication.brand_name_en,
            generic_name=medication.generic_name_en,
            generic_name_en=medication.generic_name_en,
            generic_slug=medication.generic_slug,
            brand_slug=medication.brand_slug,
            strength_raw=medication.strength,
            dosage_form=medication.form,
            manufacturer=medication.manufacturer,
            company_name=medication.company_name,
            company_slug=medication.company_slug,
        )


class MedicationPrescription(BaseModel):
    """Prescription-level instructions for one medication.

    These values describe how the patient is instructed to use the product and
    never come from the DrugYab catalog. Fields that are unknown stay ``None``;
    nothing is inferred or fabricated.

    ``dose``/``dose_unit``/``frequency`` mirror the legacy ``amount``/
    ``dose_unit``/``frequency`` fields for backward compatibility: producers
    write both, consumers may read either. ``quantity``, ``duration``,
    ``route`` and ``instructions`` are not populated by any current pipeline.
    """

    model_config = ConfigDict(frozen=True)

    dose: str | None = Field(default=None, max_length=50)
    dose_unit: str | None = Field(default=None, max_length=50)
    quantity: str | None = Field(default=None, max_length=100)
    frequency: str | None = Field(default=None, max_length=100)
    duration: str | None = Field(default=None, max_length=100)
    route: str | None = Field(default=None, max_length=50)
    instructions: str | None = Field(default=None, max_length=1000)

    @field_validator("quantity", "duration")
    @classmethod
    def reject_negative_numeric(cls, value: str | None) -> str | None:
        """Reject clearly impossible negative values; text stays free-form."""

        if value is None:
            return value
        number = _parse_signed_number(value)
        if number is not None and number < 0:
            raise ValueError(f"{value!r} must not be negative")
        return value


class MedicationProvenance(BaseModel):
    """Where a medication record came from and its verification state."""

    model_config = ConfigDict(frozen=True)

    source: MedicationSource | str = MedicationSource.MANUAL
    confidence: float | None = None
    verification_status: str = "unverified"


class Medication(BaseModel):
    """Canonical application-level medication.

    Composes the catalog snapshot, the prescription and provenance while
    keeping the legacy ``name``/``amount``/``frequency``/``dose_unit``/
    ``catalog_id`` fields for backward compatibility.
    """

    model_config = ConfigDict(frozen=True)

    name: str = ""
    amount: str = ""
    frequency: str = ""
    dose_unit: str | None = None
    catalog_id: int | None = None
    catalog: MedicationCatalogSnapshot | None = None
    prescription: MedicationPrescription | None = None
    provenance: MedicationProvenance | None = None

    @classmethod
    def from_resolved(
        cls,
        resolved: ResolvedMedication,
        *,
        name: str | None = None,
        prescription: MedicationPrescription | None = None,
        provenance: MedicationProvenance | None = None,
    ) -> Medication:
        """Compose the canonical medication from a resolved catalog row.

        The legacy ``amount`` mirror is derived from ``prescription.dose`` +
        ``dose_unit`` so there is a single structured source for the dose.
        """

        display_name = name if name is not None else resolved.display_name
        dose_unit = resolved.dose_unit or None
        prescription = prescription or MedicationPrescription(dose_unit=dose_unit)

        amount_parts: list[str] = []
        if prescription.dose:
            amount_parts.append(prescription.dose)
        if prescription.dose and dose_unit:
            amount_parts.append(dose_unit)

        return cls(
            name=display_name,
            amount=" ".join(amount_parts) if amount_parts else "",
            frequency=prescription.frequency or "",
            dose_unit=dose_unit,
            catalog_id=resolved.id,
            catalog=resolved.catalog or MedicationCatalogSnapshot.from_catalog(resolved),
            prescription=prescription,
            provenance=provenance or MedicationProvenance(source=MedicationSource.MANUAL),
        )


class MedicationResolution(BaseModel):
    """The deterministic result of resolving one manual or OCR query."""

    model_config = ConfigDict(frozen=True)

    query: str
    normalized_query: str
    source: MedicationSource
    medications: tuple[ResolvedMedication, ...] = Field(default_factory=tuple)

    @property
    def candidates(self) -> tuple[ResolvedMedication, ...]:
        """Semantic alias for callers that treat search results as candidates."""

        return self.medications

    @property
    def results(self) -> tuple[ResolvedMedication, ...]:
        """Compatibility alias for search-oriented callers."""

        return self.medications


# Concise aliases for consumers that use the architecture's generic names.
MedicationMatch = ResolvedMedication
ResolutionSource = MedicationSource
