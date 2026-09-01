"""DrugYab catalog search quality: bilingual, partial, brand, strength input."""

from __future__ import annotations

from app.modules.medications.infrastructure.catalog import DarooyabCatalog


def _search(query: str, limit: int = 3):
    return DarooyabCatalog().search(query, limit=limit)


def test_english_generic_and_partial_input() -> None:
    full = _search("Metformin")
    partial = _search("metfor")
    assert full
    assert partial
    assert all(med.generic_name_en == "Metformin" for med in full)
    assert any("metfor" in (med.brand_name_en or "").lower() for med in partial)


def test_persian_generic_and_partial_input() -> None:
    full = _search("متفورمین")
    partial = _search("متفور")
    assert full
    assert partial
    assert all(med.generic_name_en == "Metformin" for med in full)


def test_brand_search_case_insensitive() -> None:
    upper = _search("DUPHALOSE")
    lower = _search("duphalose")
    assert upper
    assert upper[0].brand_name_en == lower[0].brand_name_en
    assert upper[0].strength == "10g/15ml/240ml"


def test_strength_containing_english_input() -> None:
    results = _search("Metformin 500")
    assert results
    assert all("metformin" in (med.generic_name_en or "").lower() for med in results)
    assert any("500" in (med.strength or "").lower() for med in results)


def test_strength_containing_persian_digit_input() -> None:
    results = _search("متفورمین ۵۰۰")
    assert results
    assert all("metformin" in (med.generic_name_en or "").lower() for med in results)
    assert any("500" in (med.strength or "").lower() for med in results)


def test_strength_only_input_finds_products() -> None:
    results = _search("500 mg", limit=5)
    assert results
    assert any("500mg" in (med.strength or "").lower() for med in results)


def test_catalog_rows_expose_distinguishing_candidate_fields() -> None:
    results = _search("Metformin 500", limit=5)
    assert len(results) >= 2
    medication = results[0]
    assert medication.id
    assert medication.brand_name_en or medication.brand_name_fa
    assert medication.generic_name_en == "Metformin"
    assert medication.strength
    assert medication.form
    assert medication.manufacturer
    assert medication.company_slug
