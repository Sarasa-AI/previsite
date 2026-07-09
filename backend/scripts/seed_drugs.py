#!/usr/bin/env python3
"""Seed generic_drugs, brand_drugs, and drug_aliases with Master Bagherzadeh's formulary."""

import asyncio
import logging
import re
import sys
from pathlib import Path

from sqlalchemy import delete, select

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.database import get_async_session  # noqa: E402
from app.models.drug import BrandDrug, DrugAlias, GenericDrug  # noqa: E402
from app.services.drug_matcher import drug_matcher  # noqa: E402

logger = logging.getLogger(__name__)

_VOWELS = frozenset("aeiou")
_PERSIAN_RE = re.compile(r"[\u0600-\u06FF]")


def _is_persian(term: str) -> bool:
    return bool(_PERSIAN_RE.search(term))


def generate_typo_variants(term: str) -> list[str]:
    """Build common OCR typo variants for Latin drug names."""
    cleaned = term.strip()
    if not cleaned or _is_persian(cleaned):
        return []

    lower = cleaned.lower()
    variants: set[str] = set()

    for index, char in enumerate(lower):
        if char in _VOWELS:
            variant = lower[:index] + lower[index + 1 :]
            if len(variant) >= 4:
                variants.add(variant)

    if "i" in lower:
        variants.add(lower.replace("i", "l"))
    if "l" in lower:
        variants.add(lower.replace("l", "i"))

    if lower.endswith("ine"):
        variants.add(lower[:-1])
    if lower.endswith("in"):
        variants.add(lower[:-1])

    variants.discard(lower)
    return sorted(variants)


def generate_concatenated_variants(term: str) -> list[str]:
    """Build OCR variants where dosage digits are glued to brand names."""
    cleaned = term.strip()
    if not cleaned or _is_persian(cleaned):
        return []

    lower = cleaned.lower()
    return [f"{lower}{suffix}" for suffix in ("250", "500", "850", "1000")]


def _drug(
    generic_name: str,
    category: str,
    *,
    brands: list[str] | None = None,
    persian: list[str] | None = None,
    aliases: list[str] | None = None,
) -> dict:
    """Build a normalized seed entry with auto-generated Latin typo aliases."""
    brand_names = list(brands or [])
    alias_names = list(aliases or [])

    for persian_name in persian or []:
        if persian_name not in brand_names:
            brand_names.append(persian_name)

    auto_aliases: set[str] = set()
    for source in [generic_name, *brand_names]:
        if not _is_persian(source):
            auto_aliases.update(generate_typo_variants(source))
            auto_aliases.update(generate_concatenated_variants(source))

    for alias in alias_names:
        auto_aliases.add(alias)

    for brand in brand_names:
        auto_aliases.discard(brand.lower())
    auto_aliases.discard(generic_name.lower())

    return {
        "generic_name": generic_name,
        "category": category,
        "brands": brand_names,
        "aliases": sorted(auto_aliases),
    }


# Master Bagherzadeh's Endocrinology & Metabolism formulary.
BAGHERZADEH_FORMULARY: list[dict] = [
    # ── Diabet's Drug ──────────────────────────────────────────────────────
    _drug("Acarbose", "Diabet's Drug", persian=["آکاربوز"]),
    _drug("Metformin/Rosiglitazone", "Diabet's Drug", brands=["Avamet"]),
    _drug("Metformin", "Diabet's Drug", brands=["Glucophage", "Glomet", "Metformix", "Avano", "Avanomet", "Metfortex", "Tehran Chemie"], persian=["متفورمین", "گلوکوفاژ", "متفورتکس"]),
    _drug("Gliclazide", "Diabet's Drug", brands=["Diabezid"], persian=["دیابزید"]),
    _drug("Empagliflozin", "Diabet's Drug", brands=["Empadiance", "Empajent", "Empo", "Gloripa", "Glorenta", "Synoripa"], persian=["امپاژنت"]),
    _drug("Dapagliflozin", "Diabet's Drug", brands=["Gloxiga"]),
    _drug("Pioglitazone", "Diabet's Drug", brands=["Glutazon"]),
    _drug("Linagliptin", "Diabet's Drug", brands=["Melijent", "Melijent-M", "Glose-Lin"]),
    _drug("Sitagliptin", "Diabet's Drug", brands=["Zimptin", "Zipmet"], persian=["زیپمت"]),
    _drug("Repaglinide", "Diabet's Drug", brands=["paglimet", "Paglino", "Palino-M"]),
    _drug("Glyburide", "Diabet's Drug"),
    _drug("Empagliflozin/Metformin/Linagliptin", "Diabet's Drug", brands=["Glotrio"]),
    _drug("Clopidogrel", "Diabet's Drug", persian=["کلوپیدوگرل"]),
    # ── Thyroid's Drug ─────────────────────────────────────────────────────
    _drug("Levothyroxine", "Thyroid's Drug", brands=["Euthyrox", "Levoxine"], persian=["یوتیراکس", "لووکسین"]),
    _drug("Methimazole", "Thyroid's Drug", brands=["Methimazol"], persian=["متی مازول"]),
    _drug("Propylthiouracil", "Thyroid's Drug", persian=["پروپیل تیوراسیل"]),
    # ── Lipid's Drug ───────────────────────────────────────────────────────
    _drug("Atorvastatin", "Lipid's Drug", brands=["Atorexin"], persian=["آتورواستاتین", "آتورکسین"]),
    _drug("Rosuvastatin", "Lipid's Drug", brands=["Ropixon"], persian=["روزوواستاتین"]),
    _drug("Ezetimibe", "Lipid's Drug", brands=["Ezetimab"]),
    _drug("Fenofibrate", "Lipid's Drug", brands=["Fenofibrat"]),
    _drug("Gemfibrozil", "Lipid's Drug", persian=["جم فیبروزیل"]),
    _drug("Silymarin", "Lipid's Drug", brands=["Livergol"], persian=["لیورگل"]),
    # ── Insuline ───────────────────────────────────────────────────────────
    _drug("Insulin Glulisine", "Insuline", brands=["Apidra"], persian=["آپیدرا"]),
    _drug("Insulin Detemir", "Insuline", brands=["Detemir", "Levemir"], persian=["لومیر"]),
    _drug("Insulin Glargine", "Insuline", brands=["Glain", "Toujeo", "Masiza"], persian=["توژئو"]),
    _drug("Insulin Aspart", "Insuline", brands=["Novorapid"], persian=["نووراپید"]),
    _drug("Insulin Aspart/Insulin Aspart Protamine", "Insuline", brands=["Novomix"], persian=["نوومیکس"]),
    _drug("NPH Insulin", "Insuline", brands=["NPH"]),
    _drug("Insulin Regular", "Insuline", brands=["Regular", "Rapidsulin"], persian=["انسولین رگولار", "قلم انسولین"]),
    _drug("Insulin Degludec", "Insuline", brands=["Melitide"]),
    # ── HTN's Drug ─────────────────────────────────────────────────────────
    _drug("Amlodipine", "HTN's Drug", brands=["Amlodipin"], persian=["آملودیپین"]),
    _drug("Telmisartan", "HTN's Drug", brands=["Arbicor"]),
    _drug("Diltiazem", "HTN's Drug"),
    _drug("Enalapril", "HTN's Drug", persian=["انالاپریل"]),
    _drug("Hydrochlorothiazide", "HTN's Drug"),
    _drug("Losartan", "HTN's Drug", persian=["لوزارتان"]),
    _drug("Losartan/Hydrochlorothiazide", "HTN's Drug", brands=["Losartan.H", "Synomix"], persian=["لوزارتان اچ"]),
    _drug("Indapamide", "HTN's Drug", brands=["Natrilix SR"]),
    _drug("Prazosin", "HTN's Drug"),
    _drug("Propranolol", "HTN's Drug", persian=["پروپرانولول"]),
    _drug("Isosorbide Mononitrate", "HTN's Drug", brands=["Sustac"]),
    _drug("Terazosin", "HTN's Drug"),
    _drug("Valsartan", "HTN's Drug"),
    _drug("Valsartan/Hydrochlorothiazide", "HTN's Drug", brands=["Valsartan.H", "Valzodec-Hct"]),
    _drug("Valsartan/Amlodipine", "HTN's Drug", brands=["Valzomix"], persian=["والزومیکس"]),
    _drug("Valsartan/Amlodipine/Hydrochlorothiazide", "HTN's Drug", brands=["Valzomix-Hct"]),
    _drug("Telmisartan/Hydrochlorothiazide", "HTN's Drug", brands=["Telmyc H"]),
    # ── PCOS & Hormonal Drug ───────────────────────────────────────────────
    _drug("Cyproheptadine", "PCOS & Hormonal Drug", brands=["Contrasmine"]),
    _drug("Cyproterone Acetate", "PCOS & Hormonal Drug", brands=["Cypritron acetate"]),
    _drug("Cyproterone/Ethinylestradiol", "PCOS & Hormonal Drug", brands=["Cyproterone compound"], persian=["سیپروترون کامپاند"]),
    _drug("Dydrogesterone", "PCOS & Hormonal Drug", brands=["Duphaston"], persian=["دوفاستون"]),
    _drug("Conjugated Estrogens", "PCOS & Hormonal Drug", brands=["Estromarine", "Marolin"]),
    _drug("Medroxyprogesterone", "PCOS & Hormonal Drug", brands=["Medroxi progestrone"], persian=["مدروکسی پروژسترون"]),
    _drug("Letrozole", "PCOS & Hormonal Drug", brands=["Rokin"], persian=["روکین"]),
    _drug("Spironolactone", "PCOS & Hormonal Drug", persian=["اسپیرونولاکتون"]),
    _drug("Drospirenone/Ethinylestradiol", "PCOS & Hormonal Drug", brands=["Yasmin"]),
    # ── Prolactin ──────────────────────────────────────────────────────────
    _drug("Cabergoline", "Prolactin", brands=["Dostinex"], persian=["کابرگولین", "داستینکس"]),
    # ── Bone/Parathyroid ───────────────────────────────────────────────────
    _drug("Alendronate", "Bone/Parathyroid"),
    _drug("Calcium/Magnesium/Zinc", "Bone/Parathyroid", brands=["Ca-Mg-Zinc"]),
    _drug("Calcitriol", "Bone/Parathyroid"),
    _drug("Calcium Carbonate", "Bone/Parathyroid"),
    _drug("Leuprolide", "Bone/Parathyroid", brands=["Diphereline"]),
    _drug("Teriparatide", "Bone/Parathyroid", brands=["Forteo"]),
    _drug("Ibandronate", "Bone/Parathyroid", brands=["Boniva"]),
    _drug("Risedronate", "Bone/Parathyroid", brands=["Osteofos"]),
    # ── Obesity ────────────────────────────────────────────────────────────
    _drug("Orlistat", "Obesity", brands=["Venustat"], persian=["اورلیستات", "وناستات"]),
    _drug("Topiramate", "Obesity", persian=["توپیرامات"]),
    # ── Psychological ──────────────────────────────────────────────────────
    _drug("Alprazolam", "Psychological"),
    _drug("Venlafaxine", "Psychological", brands=["Alventa"]),
    _drug("Sertraline", "Psychological", brands=["Asentra"]),
    _drug("Chlordiazepoxide", "Psychological"),
    _drug("Citalopram", "Psychological"),
    _drug("Escitalopram", "Psychological"),
    _drug("Fluoxetine", "Psychological"),
    _drug("Gabapentin", "Psychological"),
    _drug("Paroxetine", "Psychological", brands=["Luxeta"]),
    _drug("Pregabalin", "Psychological", brands=["Lyriver"]),
    _drug("Melatonin", "Psychological"),
    # ── Supplements ────────────────────────────────────────────────────────
    _drug("Calcium Supplement", "Supplements", brands=["Calcicare", "Osteocare"]),
    _drug("Diabetes Supplement", "Supplements", brands=["Diabegold", "Diaberese", "Diabetone"]),
    _drug("Hair Supplement", "Supplements", brands=["Haironik", "Hair-vit"]),
    _drug("Magnesium Supplement", "Supplements", brands=["Magnifort", "Magtrea ZMA"]),
    _drug("Multivitamin/Mineral", "Supplements", brands=["Multi vitamin Mineral", "Nevazin"]),
    _drug("Bone Supplement", "Supplements", brands=["Unibone"]),
    _drug("Vitamin B1", "Supplements"),
    _drug("Vitamin D3", "Supplements"),
    _drug("Zinc Supplement", "Supplements", brands=["Zinc plus"]),
]

# General-purpose medications retained from the original seed set.
LEGACY_DRUG_SEED_DATA: list[dict] = [
    _drug("Aspirin", "Antiplatelet", brands=["آسپرین"], aliases=["اسپرین", "Asprin"]),
    _drug("Pantoprazole", "PPI", brands=["پنتوپرازول", "Pantoloc"], aliases=["پنتوپرازل", "Pantoprazol"]),
    _drug("Metoprolol", "Beta-blocker", brands=["متوپرولول", "Metoral"], aliases=["متوپرولل"]),
    _drug("Omeprazole", "PPI", brands=["امپرازول"], aliases=["امپرازل", "Omeprazol"]),
    _drug("Simvastatin", "Statin", brands=["سیمواستاتین", "Zocor"], aliases=["سیمواستاتن", "Simvastatln"]),
    _drug("Warfarin", "Anticoagulant", brands=["وارفارین"], aliases=["وارفرین", "Warfarln"]),
    _drug("Losartan", "Antihypertensive", brands=["Cosaar"], aliases=["Luzartan"]),
    _drug("Levothyroxine", "Thyroid", aliases=["لووتیروکسین", "لووتیروکسن", "Levothyroxin"]),
    _drug("Metformin", "Antidiabetic", aliases=["متفورمن"]),
    _drug("Atorvastatin", "Statin", brands=["Lipitor"], aliases=["آتورواستاتن"]),
    _drug("Amlodipine", "Antihypertensive", aliases=["آملودیپن"]),
    _drug("Clopidogrel", "Antiplatelet", brands=["Plavix"]),
]


def _merge_seed_entries(*sources: list[dict]) -> list[dict]:
    """Merge seed rows by generic_name, combining brands and aliases."""
    merged: dict[str, dict] = {}

    for source in sources:
        for entry in source:
            name = entry["generic_name"]
            if name not in merged:
                merged[name] = {
                    "generic_name": name,
                    "category": entry["category"],
                    "brands": [],
                    "aliases": [],
                }

            existing = merged[name]
            for brand in entry["brands"]:
                if brand not in existing["brands"]:
                    existing["brands"].append(brand)
            for alias in entry["aliases"]:
                if alias not in existing["aliases"]:
                    existing["aliases"].append(alias)

    return sorted(merged.values(), key=lambda item: item["generic_name"].lower())


DRUG_SEED_DATA: list[dict] = _merge_seed_entries(BAGHERZADEH_FORMULARY, LEGACY_DRUG_SEED_DATA)


async def _upsert_generic(
    db,
    drug_data: dict,
) -> GenericDrug:
    result = await db.execute(
        select(GenericDrug).where(GenericDrug.generic_name == drug_data["generic_name"])
    )
    generic = result.scalar_one_or_none()
    if generic is None:
        generic = GenericDrug(
            generic_name=drug_data["generic_name"],
            category=drug_data["category"],
        )
        db.add(generic)
        await db.flush()
        return generic

    generic.category = drug_data["category"]
    await db.execute(delete(BrandDrug).where(BrandDrug.generic_id == generic.id))
    await db.execute(delete(DrugAlias).where(DrugAlias.generic_id == generic.id))
    return generic


async def seed_drugs(*, refresh_matcher: bool = True) -> None:
    """Idempotently seed the drug formulary and optionally warm the matcher cache."""
    async with get_async_session() as db:
        try:
            seeded_names = {entry["generic_name"] for entry in DRUG_SEED_DATA}

            result = await db.execute(select(GenericDrug))
            existing_generics = result.scalars().all()
            for generic in existing_generics:
                if generic.generic_name not in seeded_names:
                    await db.delete(generic)

            for drug_data in DRUG_SEED_DATA:
                generic = await _upsert_generic(db, drug_data)

                for brand_name in drug_data["brands"]:
                    db.add(BrandDrug(brand_name=brand_name, generic_id=generic.id))

                for alias_name in drug_data["aliases"]:
                    db.add(DrugAlias(alias_name=alias_name, generic_id=generic.id))

            await db.commit()

            result = await db.execute(select(GenericDrug))
            count = len(result.scalars().all())
            logger.info("Seeded %s generic drugs from Master Bagherzadeh formulary", count)

            if refresh_matcher:
                await drug_matcher.refresh_cache(db)
                logger.info("Drug matcher cache reloaded")
        except Exception:
            await db.rollback()
            raise


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    asyncio.run(seed_drugs())


if __name__ == "__main__":
    main()
