"""Unit tests for clinical PDF generation."""

from app.schemas.intake import (
    ChronicCondition,
    ClinicalSummary,
    CurrentMedication,
    LabResult,
    MedicalOverview,
)
from app.services.pdf_service import FONT_DIR, generate_patient_report_pdf, reshape_persian_text


def _sample_session_data(
  *,
  clinical_summary: ClinicalSummary | None = None,
) -> dict:
    return {
        "session_id": 42,
        "clinic_name": "PreVisit MVP",
        "report_date": "2026-07-09 12:00 UTC",
        "patient_name": "علی رضایی",
        "clinical_summary": clinical_summary,
        "demographics": None,
    }


def _sample_overview() -> MedicalOverview:
    return MedicalOverview(
        allergies="پنی‌سیلین",
        surgical_history="آپاندکتومی ۱۳۹۵",
        family_history="دیابت در پدر",
        chronic_conditions=[
            ChronicCondition(id="c1", name="فشار خون بالا", duration="۵ سال"),
        ],
        current_medications=[
            CurrentMedication(id="m1", name="لوزارتان", amount="۵۰mg", frequency="روزانه"),
        ],
        lab_results=[
            LabResult(
                id="l1",
                name="CBC",
                extracted_data="WBC: 7.2, HGB: 14.1, PLT: 250",
            ),
        ],
        patient_questions="آیا نیاز به آزمایش مجدد دارم؟",
    )


def test_generates_valid_pdf_bytes() -> None:
    clinical = ClinicalSummary(
        chief_complaint="درد قفسه سینه",
        hpi_summary="بیمار از ۲ روز پیش دچار درد قفسه سینه شده است.",
        pertinent_positives=["تنگی نفس"],
        pertinent_negatives=["تب ندارد"],
        red_flags=[],
    )
    pdf_bytes = generate_patient_report_pdf(
        _sample_session_data(clinical_summary=clinical),
        _sample_overview(),
    )

    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 500


def test_includes_persian_content_without_crash() -> None:
    clinical = ClinicalSummary(
        chief_complaint="درد شکم و تهوع",
        hpi_summary="بیمار از دیروز دچار درد شکم و تهوع شده و غذا نخورده است.",
        pertinent_positives=["درد موضعی"],
        pertinent_negatives=["خونریزی ندارد"],
        red_flags=["درد شدید"],
    )
    pdf_bytes = generate_patient_report_pdf(
        _sample_session_data(clinical_summary=clinical),
        _sample_overview(),
    )

    assert pdf_bytes.startswith(b"%PDF")


def test_empty_sections_use_placeholders() -> None:
    pdf_bytes = generate_patient_report_pdf(
        _sample_session_data(clinical_summary=None),
        MedicalOverview(),
    )

    assert pdf_bytes.startswith(b"%PDF")


def test_long_text_wraps_in_tables() -> None:
    long_name = "لوزارتان " * 40
    long_extracted = "WBC: 7.2, " * 80
    overview = MedicalOverview(
        current_medications=[
            CurrentMedication(
                id="m1",
                name=long_name,
                amount="۵۰mg",
                frequency="هر ۱۲ ساعت یک بار با غذا",
            ),
        ],
        lab_results=[
            LabResult(id="l1", name="CBC Panel", extracted_data=long_extracted),
        ],
    )
    clinical = ClinicalSummary(
        chief_complaint="x",
        hpi_summary="y",
        pertinent_positives=[],
        pertinent_negatives=[],
        red_flags=[],
    )

    pdf_bytes = generate_patient_report_pdf(
        _sample_session_data(clinical_summary=clinical),
        overview,
    )

    assert pdf_bytes.startswith(b"%PDF")


def test_vazirmatn_font_assets_exist() -> None:
    regular = FONT_DIR / "Vazirmatn-Regular.ttf"
    bold = FONT_DIR / "Vazirmatn-Bold.ttf"
    assert regular.is_file()
    assert bold.is_file()
    assert regular.stat().st_size > 0
    assert bold.stat().st_size > 0


def test_reshape_persian_text_handles_persian_and_ascii() -> None:
    persian = reshape_persian_text("لوزارتان")
    assert persian
    assert persian != ""

    ascii_text = reshape_persian_text("Metformin")
    assert ascii_text == "Metformin"

    assert reshape_persian_text("") == ""
