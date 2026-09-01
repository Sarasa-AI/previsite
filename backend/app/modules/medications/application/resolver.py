"""Shared manual and OCR medication resolver."""

from __future__ import annotations

from typing import Protocol

from app.modules.medications.domain.models import (
    CatalogMedication,
    MedicationCatalogSnapshot,
    MedicationResolution,
    MedicationSource,
    ResolvedMedication,
)
from app.modules.medications.domain.rules import get_dose_unit, medication_display_name
from app.modules.medications.infrastructure.catalog import DarooyabCatalog


class MedicationCatalog(Protocol):
    def search(self, query: str, limit: int = 20) -> tuple[CatalogMedication, ...]: ...


class MedicationResolver:
    """Resolve every medication query through one catalog-backed boundary."""

    def __init__(self, catalog: MedicationCatalog | None = None) -> None:
        self._catalog = catalog if catalog is not None else DarooyabCatalog()

    def resolve(
        self,
        query: str,
        *,
        source: MedicationSource | str = MedicationSource.MANUAL,
        limit: int = 20,
    ) -> MedicationResolution:
        normalized_query = query.strip()
        resolved_source = MedicationSource(source)
        catalog_medications = self._catalog.search(normalized_query, limit=limit)

        medications = tuple(
            self._resolve_medication(medication, query=normalized_query)
            for medication in catalog_medications
        )
        return MedicationResolution(
            query=query,
            normalized_query=normalized_query,
            source=resolved_source,
            medications=medications,
        )

    def resolve_manual(self, query: str, *, limit: int = 20) -> MedicationResolution:
        return self.resolve(query, source=MedicationSource.MANUAL, limit=limit)

    def resolve_ocr(self, query: str, *, limit: int = 20) -> MedicationResolution:
        return self.resolve(query, source=MedicationSource.OCR, limit=limit)

    @staticmethod
    def _resolve_medication(
        medication: CatalogMedication,
        *,
        query: str,
    ) -> ResolvedMedication:
        return ResolvedMedication(
            **medication.model_dump(),
            display_name=medication_display_name(
                query=query,
                brand_name_fa=medication.brand_name_fa,
                brand_name_en=medication.brand_name_en,
                generic_name_en=medication.generic_name_en,
            ),
            dose_unit=get_dose_unit(
                form=medication.form,
                brand_name_en=medication.brand_name_en,
                generic_name_en=medication.generic_name_en,
                brand_name_fa=medication.brand_name_fa,
                strength=medication.strength,
            ),
            catalog=MedicationCatalogSnapshot.from_catalog(medication),
        )


Resolver = MedicationResolver
