"""Pure medication search and dose-unit rules."""

from __future__ import annotations


def uses_latin_script(value: str) -> bool:
    """Match the language check used by the existing Darooyab search UI."""

    return any("a" <= character.lower() <= "z" for character in value)


def medication_display_name(
    *,
    query: str,
    brand_name_fa: str | None,
    brand_name_en: str | None,
    generic_name_en: str | None,
) -> str:
    """Choose the same bilingual result label as ``drug_search.py``."""

    if uses_latin_script(query):
        return brand_name_en or brand_name_fa or generic_name_en or ""
    return brand_name_fa or brand_name_en or generic_name_en or ""


def get_dose_unit(
    form: str | None,
    brand_name_en: str | None = "",
    generic_name_en: str | None = "",
    brand_name_fa: str | None = "",
    strength: str | None = "",
) -> str:
    """Infer the consumption unit with the precedence from ``drug_search.py``."""

    normalized_form = (form or "").upper().strip()
    brand_en = (brand_name_en or "").upper().strip()
    generic_en = (generic_name_en or "").upper().strip()
    brand_fa = (brand_name_fa or "").strip()
    strength_text = (strength or "").upper().strip()
    searchable_text_en = f"{brand_en} {generic_en}"
    searchable_all_en = f"{searchable_text_en} {strength_text}"

    if "INSULIN" in searchable_text_en or "انسولین" in brand_fa:
        return "واحد (Unit)"

    if (
        "NEBULIZATION" in searchable_all_en
        or "NEBULIZER" in searchable_all_en
        or "NEBULI" in searchable_all_en
        or "NEBULE" in searchable_all_en
        or "نبولایز" in brand_fa
        or "نبولایزر" in brand_fa
        or "نبول" in brand_fa
    ):
        return "میلی‌لیتر"

    if (
        "INHALER" in searchable_all_en
        or "MDI" in searchable_all_en
        or "METERED DOSE" in searchable_all_en
        or "PUFF" in searchable_all_en
        or "INHALATION AEROSOL" in searchable_all_en
        or "اسپری" in brand_fa
        or "اینهالر" in brand_fa
        or "استنشاقی" in brand_fa
    ):
        return "پاف"

    if (
        normalized_form == "SUSPENSION"
        or "SUSP" in searchable_all_en
        or "SUSPENSION" in searchable_all_en
        or "سوسپانسیون" in brand_fa
    ):
        return "میلی‌لیتر"

    if normalized_form == "SYRUP" or "SYRUP" in searchable_all_en or "شربت" in brand_fa:
        return "میلی‌لیتر"

    if (
        normalized_form == "SOLUTION"
        or "SOLUTION" in searchable_all_en
        or "محلول" in brand_fa
    ):
        return "میلی‌لیتر"

    if (
        normalized_form == "DROP"
        or "DROP" in searchable_all_en
        or "DROPS" in searchable_all_en
        or "قطره" in brand_fa
    ):
        return "قطره"

    if normalized_form == "LOTION" or "LOTION" in searchable_all_en or "لوسیون" in brand_fa:
        return "میلی‌لیتر"

    if (
        normalized_form in {"CREAM", "GEL", "OINT"}
        or "CREAM" in searchable_all_en
        or "GEL" in searchable_all_en
        or "OINTMENT" in searchable_all_en
        or "پماد" in brand_fa
        or "کرم" in brand_fa
        or "ژل" in brand_fa
    ):
        return "گرم"

    if normalized_form == "SPRAY":
        return "پاف"

    units_by_form = {
        "TAB": "قرص",
        "EFF": "قرص جوشان",
        "CAP": "کپسول",
        "SOFTGEL": "سافت‌ژل",
        "SACHET": "ساشه",
        "SYRUP": "میلی‌لیتر",
        "SOLUTION": "میلی‌لیتر",
        "SUSPENSION": "میلی‌لیتر",
        "DROP": "قطره",
        "AMP": "آمپول",
        "VIAL": "ویال",
        "INJ": "واحد (Unit)",
        "CREAM": "گرم",
        "GEL": "گرم",
        "OINT": "گرم",
        "LOTION": "میلی‌لیتر",
        "SPRAY": "پاف",
        "SUPP": "شیاف",
        "PATCH": "پچ",
        "SHAMPOO": "میلی‌لیتر",
        "POWDER": "واحد",
    }
    return units_by_form.get(normalized_form, "واحد")


infer_dose_unit = get_dose_unit
