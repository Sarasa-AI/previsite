"""Minimal DTOs for manual medication search."""

from pydantic import BaseModel, ConfigDict, Field

from app.modules.medications.domain.models import ResolvedMedication


class MedicationSearchResultDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    # Canonical catalog identity; ``id`` remains for legacy clients.
    catalog_id: int
    display_name: str
    brand_name: str | None = None
    brand_name_fa: str | None = None
    brand_name_en: str | None = None
    generic_name: str | None = None
    generic_name_en: str | None = None
    generic_slug: str | None = None
    brand_slug: str | None = None
    form: str | None = None
    strength: str | None = None
    manufacturer: str | None = None
    company_name: str | None = None
    company_slug: str | None = None
    dose_unit: str

    @classmethod
    def from_resolved(cls, medication: ResolvedMedication) -> "MedicationSearchResultDTO":
        data = medication.model_dump()
        catalog = medication.catalog
        return cls(
            id=data["id"],
            catalog_id=data["id"],
            display_name=data["display_name"],
            brand_name=catalog.brand_name if catalog else None,
            brand_name_fa=data.get("brand_name_fa"),
            brand_name_en=data.get("brand_name_en"),
            generic_name=catalog.generic_name if catalog else None,
            generic_name_en=data.get("generic_name_en"),
            generic_slug=catalog.generic_slug if catalog else None,
            brand_slug=catalog.brand_slug if catalog else None,
            form=data.get("form"),
            strength=data.get("strength"),
            manufacturer=data.get("manufacturer"),
            company_name=catalog.company_name if catalog else None,
            company_slug=catalog.company_slug if catalog else None,
            dose_unit=data["dose_unit"],
        )


class MedicationSearchResponseDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    query: str
    results: list[MedicationSearchResultDTO] = Field(default_factory=list)
