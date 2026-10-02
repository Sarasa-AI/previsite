from __future__ import annotations

from pathlib import Path

import pytest

from app.modules.medications.application.resolver import MedicationResolver
from app.modules.medications.domain.models import CatalogMedication, MedicationSource
from app.modules.medications.domain.rules import get_dose_unit
from app.modules.medications.infrastructure.catalog import (
    CatalogUnavailableError,
    DarooyabCatalog,
    configured_catalog_path,
)


class RecordingCatalog:
    def __init__(self, medications: tuple[CatalogMedication, ...]) -> None:
        self.medications = medications
        self.calls: list[tuple[str, int]] = []

    def search(self, query: str, limit: int = 20) -> tuple[CatalogMedication, ...]:
        self.calls.append((query, limit))
        return self.medications[:limit]


@pytest.fixture
def metformin() -> CatalogMedication:
    return CatalogMedication(
        id=101,
        brand_name_fa="گلوکوفاژ",
        brand_name_en="Glucophage",
        generic_name_en="Metformin",
        form="TAB",
        strength="500 mg",
        manufacturer="Merck",
    )


def test_manual_and_ocr_use_the_same_resolver_path(metformin: CatalogMedication) -> None:
    catalog = RecordingCatalog((metformin,))
    resolver = MedicationResolver(catalog)

    manual = resolver.resolve_manual("  Metformin  ", limit=5)
    ocr = resolver.resolve_ocr("  Metformin  ", limit=5)

    assert catalog.calls == [("Metformin", 5), ("Metformin", 5)]
    assert manual.source == MedicationSource.MANUAL
    assert ocr.source == MedicationSource.OCR
    assert manual.medications == ocr.medications
    assert manual.normalized_query == "Metformin"


def test_resolver_preserves_catalog_fields_and_enriches_result(
    metformin: CatalogMedication,
) -> None:
    resolver = MedicationResolver(RecordingCatalog((metformin,)))

    result = resolver.resolve("met", source="manual").medications[0]

    assert result.id == 101
    assert result.brand_name_fa == "گلوکوفاژ"
    assert result.brand_name_en == "Glucophage"
    assert result.generic_name_en == "Metformin"
    assert result.form == "TAB"
    assert result.strength == "500 mg"
    assert result.manufacturer == "Merck"
    assert result.display_name == "Glucophage"
    assert result.dose_unit == "قرص"


def test_resolver_prefers_persian_label_for_persian_query(
    metformin: CatalogMedication,
) -> None:
    resolver = MedicationResolver(RecordingCatalog((metformin,)))

    result = resolver.resolve("متفورمین", source=MedicationSource.OCR).medications[0]

    assert result.display_name == "گلوکوفاژ"


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"form": "TAB"}, "قرص"),
        ({"form": "CAP"}, "کپسول"),
        ({"form": "", "generic_name_en": "Insulin Glargine"}, "واحد (Unit)"),
        ({"form": "", "brand_name_en": "Salbutamol Inhaler"}, "پاف"),
        ({"form": "", "brand_name_en": "Salbutamol Nebulization"}, "میلی‌لیتر"),
        ({"form": "CREAM"}, "گرم"),
        ({"form": "UNKNOWN"}, "واحد"),
    ],
)
def test_dose_unit_rules_preserve_existing_precedence(kwargs: dict, expected: str) -> None:
    assert get_dose_unit(**kwargs) == expected


def test_catalog_path_can_be_configured_by_environment(monkeypatch, tmp_path: Path) -> None:
    configured = tmp_path / "real-catalog.db"
    monkeypatch.setenv("MEDICATION_CATALOG_PATH", str(configured))

    assert configured_catalog_path() == configured


def test_missing_catalog_fails_clearly_without_creating_a_database(tmp_path: Path) -> None:
    missing = tmp_path / "darooyab.db"

    with pytest.raises(CatalogUnavailableError, match="MEDICATION_CATALOG_PATH"):
        DarooyabCatalog(missing)

    assert not missing.exists()
