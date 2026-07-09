import pytest

from app.models.drug import BrandDrug, DrugAlias, GenericDrug
from app.services.drug_matcher import DrugMatcher, drug_matcher


async def _seed_losartan(db) -> None:
    generic = GenericDrug(generic_name="Losartan", category="Antihypertensive")
    db.add(generic)
    await db.flush()
    db.add(BrandDrug(brand_name="لوزارتان", generic_id=generic.id))
    db.add(DrugAlias(alias_name="لوزارتن", generic_id=generic.id))
    await db.commit()


@pytest.mark.asyncio
async def test_match_drug_resolves_ocr_typo_alias(db) -> None:
    await _seed_losartan(db)
    matcher = DrugMatcher()
    await matcher.refresh_cache(db)

    result = matcher.match_drug("لوزارتن")
    assert result is not None
    assert result["generic_name"] == "Losartan"
    assert result["match_type"] == "alias"
    assert result["score"] >= 85


@pytest.mark.asyncio
async def test_match_drug_resolves_brand_name(db) -> None:
    await _seed_losartan(db)
    matcher = DrugMatcher()
    await matcher.refresh_cache(db)

    result = matcher.match_drug("لوزارتان")
    assert result is not None
    assert result["generic_name"] == "Losartan"
    assert result["match_type"] == "brand"
    assert result["score"] >= 85


@pytest.mark.asyncio
async def test_match_drug_returns_none_below_threshold(db) -> None:
    await _seed_losartan(db)
    matcher = DrugMatcher()
    await matcher.refresh_cache(db)

    assert matcher.match_drug("xyzabc") is None


@pytest.mark.asyncio
async def test_match_drug_returns_none_when_cache_empty() -> None:
    matcher = DrugMatcher()
    assert matcher.match_drug("Losartan") is None


async def _seed_metformin(db) -> None:
    generic = GenericDrug(generic_name="Metformin", category="Diabet's Drug")
    db.add(generic)
    await db.flush()
    db.add(BrandDrug(brand_name="Metfortex", generic_id=generic.id))
    await db.commit()


@pytest.mark.asyncio
async def test_match_drug_resolves_concatenated_brand_name(db) -> None:
    await _seed_metformin(db)
    matcher = DrugMatcher()
    await matcher.refresh_cache(db)

    result = matcher.match_drug("Metfortex500")
    assert result is not None
    assert result["generic_name"] == "Metformin"
    assert result["match_type"] == "brand"
    assert result["score"] >= 85


@pytest.mark.asyncio
async def test_match_drug_resolves_metfortex_brand(db) -> None:
    await _seed_metformin(db)
    matcher = DrugMatcher()
    await matcher.refresh_cache(db)

    result = matcher.match_drug("Metfortex")
    assert result is not None
    assert result["generic_name"] == "Metformin"
    assert result["match_type"] == "brand"
    assert result["score"] >= 85
    await _seed_losartan(db)
    await drug_matcher.refresh_cache(db)

    result = drug_matcher.match_drug("Losartan")
    assert result is not None
    assert result["generic_name"] == "Losartan"
    assert result["match_type"] == "generic"
