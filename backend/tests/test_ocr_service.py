from app.services.medical_overview_service import (
    format_medication_for_summary,
    validate_file_link_id,
)
from app.services import ocr_service
from app.services.drug_matcher import DrugMatcher
from app.services.ocr_service import (
    DEFAULT_MEDICATION_AMOUNT,
    DEFAULT_MEDICATION_FREQUENCY,
    TesseractMeta,
    _correct_image_orientation,
    _extract_cgm_readings,
    _extract_lab_pairs,
    extract_lab_values_ocr,
    extract_medication_ocr,
    preprocess_image_for_ocr,
)
from app.schemas.intake import CurrentMedication, MedicalOverview
from app.models.drug import BrandDrug, DrugAlias, GenericDrug
import cv2
import numpy as np
import pytest


def _mock_tesseract(text: str, meta: TesseractMeta | None = None):
    resolved_meta = meta or TesseractMeta(avg_confidence=90.0)
    return lambda _processed: (text, resolved_meta)


async def _seed_losartan_for_ocr(db) -> DrugMatcher:
    generic = GenericDrug(generic_name="Losartan", category="Antihypertensive")
    db.add(generic)
    await db.flush()
    db.add(BrandDrug(brand_name="لوزارتان", generic_id=generic.id))
    db.add(DrugAlias(alias_name="لوزارتن", generic_id=generic.id))
    await db.commit()

    matcher = DrugMatcher()
    await matcher.refresh_cache(db)
    return matcher


async def _seed_losartan_and_metformin_for_ocr(db) -> DrugMatcher:
    losartan = GenericDrug(generic_name="Losartan", category="Antihypertensive")
    metformin = GenericDrug(generic_name="Metformin", category="Diabet's Drug")
    db.add(losartan)
    db.add(metformin)
    await db.flush()
    db.add(BrandDrug(brand_name="لوزارتان", generic_id=losartan.id))
    db.add(BrandDrug(brand_name="متفورمین", generic_id=metformin.id))
    await db.commit()

    matcher = DrugMatcher()
    await matcher.refresh_cache(db)
    return matcher


@pytest.mark.asyncio
async def test_extract_medication_ocr_returns_standardized_name(monkeypatch, db) -> None:
    matcher = await _seed_losartan_for_ocr(db)
    monkeypatch.setattr(ocr_service, "drug_matcher", matcher)
    monkeypatch.setattr(
        ocr_service,
        "_run_tesseract_with_meta",
        _mock_tesseract("لوزارتن"),
    )

    img = np.zeros((40, 200, 3), dtype=np.uint8)
    _, encoded = cv2.imencode(".png", img)
    result = extract_medication_ocr(encoded.tobytes(), "image/png")
    assert result == [
        {
            "name": "Losartan",
            "amount": DEFAULT_MEDICATION_AMOUNT,
            "frequency": DEFAULT_MEDICATION_FREQUENCY,
        }
    ]


@pytest.mark.asyncio
async def test_extract_medication_ocr_returns_none_when_no_match(monkeypatch, db) -> None:
    matcher = await _seed_losartan_for_ocr(db)
    monkeypatch.setattr(ocr_service, "drug_matcher", matcher)
    monkeypatch.setattr(
        ocr_service,
        "_run_tesseract_with_meta",
        _mock_tesseract("Patient Name: John Doe"),
    )

    img = np.zeros((40, 200, 3), dtype=np.uint8)
    _, encoded = cv2.imencode(".png", img)
    assert extract_medication_ocr(encoded.tobytes(), "image/png") is None


def test_extract_medication_ocr_invalid_bytes() -> None:
    assert extract_medication_ocr(b"not-an-image", "image/png") is None


@pytest.mark.asyncio
async def test_extract_medication_ocr_multi_drug_persian_list(monkeypatch, db) -> None:
    matcher = await _seed_losartan_and_metformin_for_ocr(db)
    monkeypatch.setattr(ocr_service, "drug_matcher", matcher)
    monkeypatch.setattr(
        ocr_service,
        "_run_tesseract_with_meta",
        _mock_tesseract("لوزارتان\nمتفورمین"),
    )

    img = np.zeros((40, 200, 3), dtype=np.uint8)
    _, encoded = cv2.imencode(".png", img)
    result = extract_medication_ocr(encoded.tobytes(), "image/png")
    assert result == [
        {
            "name": "Losartan",
            "amount": DEFAULT_MEDICATION_AMOUNT,
            "frequency": DEFAULT_MEDICATION_FREQUENCY,
        },
        {
            "name": "Metformin",
            "amount": DEFAULT_MEDICATION_AMOUNT,
            "frequency": DEFAULT_MEDICATION_FREQUENCY,
        },
    ]


@pytest.mark.asyncio
async def test_extract_medication_ocr_partial_match_returns_matched_subset(monkeypatch, db) -> None:
    matcher = await _seed_losartan_for_ocr(db)
    monkeypatch.setattr(ocr_service, "drug_matcher", matcher)
    monkeypatch.setattr(
        ocr_service,
        "_run_tesseract_with_meta",
        _mock_tesseract("لوزارتان\nنامشخص دارو"),
    )

    img = np.zeros((40, 200, 3), dtype=np.uint8)
    _, encoded = cv2.imencode(".png", img)
    result = extract_medication_ocr(encoded.tobytes(), "image/png")
    assert result == [
        {
            "name": "Losartan",
            "amount": DEFAULT_MEDICATION_AMOUNT,
            "frequency": DEFAULT_MEDICATION_FREQUENCY,
        }
    ]


@pytest.mark.asyncio
async def test_handwriting_scenario_returns_none_with_no_match(monkeypatch, db) -> None:
    matcher = await _seed_losartan_for_ocr(db)
    monkeypatch.setattr(ocr_service, "drug_matcher", matcher)
    monkeypatch.setattr(
        ocr_service,
        "_run_tesseract_with_meta",
        _mock_tesseract(
            "scribble line one\nscribble line two",
            TesseractMeta(avg_confidence=35.0, block_word_counts=[1, 1, 1]),
        ),
    )

    img = np.zeros((40, 200, 3), dtype=np.uint8)
    _, encoded = cv2.imencode(".png", img)
    assert extract_medication_ocr(encoded.tobytes(), "image/png") is None


def test_extract_cgm_readings_from_text() -> None:
    readings = _extract_cgm_readings("110 - 8:00\n142 - 12:30")
    assert len(readings) == 2
    assert readings[0].value == "110"
    assert readings[0].time == "8:00"
    assert readings[1].value == "142"
    assert readings[1].time == "12:30"


def test_extract_lab_values_ocr_cgm_happy_path(monkeypatch) -> None:
    sample_text = "110 - 8:00\n142 - 12:30"

    monkeypatch.setattr(
        ocr_service,
        "_run_tesseract_with_meta",
        _mock_tesseract(sample_text),
    )

    img = np.zeros((40, 200, 3), dtype=np.uint8)
    _, encoded = cv2.imencode(".png", img)
    result = extract_lab_values_ocr(encoded.tobytes(), "image/png")
    assert result == "CGM: 110 @ 8:00, 142 @ 12:30"


def test_extract_lab_values_ocr_from_pdf_text(monkeypatch) -> None:
    monkeypatch.setattr(
        ocr_service,
        "_extract_pdf_text",
        lambda _file_bytes: "WBC 4.5\nHb: 13.2",
    )

    def _fail_tesseract(_processed: np.ndarray):
        raise AssertionError("Tesseract should not run for text-based PDFs")

    monkeypatch.setattr(ocr_service, "_run_tesseract_with_meta", _fail_tesseract)

    result = extract_lab_values_ocr(b"%PDF-fake", "application/pdf")
    assert result == "WBC: 4.5, Hb: 13.2"


def test_extract_lab_pairs_parses_common_cbc_keys() -> None:
    text = """
    WBC  4.5
    RBC: 4.82
    HGB - 13.2
    MCHC | 31.2
    MCH: 28.5
    Platelet 166,000
    PLT 150000
    """
    pairs = _extract_lab_pairs(text)
    assert pairs == {
        "WBC": "4.5",
        "RBC": "4.82",
        "Hb": "13.2",
        "MCHC": "31.2",
        "MCH": "28.5",
        "Platelet": "166000",
    }


def test_extract_lab_pairs_returns_empty_for_non_lab_text() -> None:
    assert _extract_lab_pairs("Patient Name: John Doe") == {}


def test_extract_lab_values_ocr_happy_path(monkeypatch) -> None:
    sample_text = "WBC 4.5\nHb: 13.2\nPlatelet: 150000"

    monkeypatch.setattr(
        ocr_service,
        "_run_tesseract_with_meta",
        _mock_tesseract(sample_text),
    )

    img = np.zeros((40, 200, 3), dtype=np.uint8)
    _, encoded = cv2.imencode(".png", img)
    result = extract_lab_values_ocr(encoded.tobytes(), "image/png")
    assert result == "WBC: 4.5, Hb: 13.2, Platelet: 150000"


def test_extract_lab_values_ocr_no_matches(monkeypatch) -> None:
    monkeypatch.setattr(
        ocr_service,
        "_run_tesseract_with_meta",
        _mock_tesseract("Patient Name: John Doe"),
    )

    img = np.zeros((40, 200, 3), dtype=np.uint8)
    _, encoded = cv2.imencode(".png", img)
    assert extract_lab_values_ocr(encoded.tobytes(), "image/png") is None


def test_extract_lab_values_ocr_invalid_bytes() -> None:
    assert extract_lab_values_ocr(b"not-an-image", "image/png") is None


def test_preprocess_image_for_ocr_returns_binary_matrix() -> None:
    img = np.full((30, 60, 3), 255, dtype=np.uint8)
    _, encoded = cv2.imencode(".png", img)
    processed = preprocess_image_for_ocr(encoded.tobytes())
    assert processed.ndim == 2
    assert processed.dtype == np.uint8
    assert processed.shape[0] > 0 and processed.shape[1] > 0


def test_correct_image_orientation_rotates_90_degrees(monkeypatch) -> None:
    monkeypatch.setattr(
        ocr_service.pytesseract,
        "image_to_osd",
        lambda _gray, config="": "Orientation in degrees: 90\nRotate: 90\n",
    )

    img = np.zeros((40, 80, 3), dtype=np.uint8)
    rotated = _correct_image_orientation(img)
    assert rotated.shape == (80, 40, 3)


def test_correct_image_orientation_keeps_upright_image(monkeypatch) -> None:
    monkeypatch.setattr(
        ocr_service.pytesseract,
        "image_to_osd",
        lambda _gray, config="": "Orientation in degrees: 0\nRotate: 0\n",
    )

    img = np.zeros((40, 80, 3), dtype=np.uint8)
    assert _correct_image_orientation(img).shape == img.shape


def test_preprocess_image_for_ocr_applies_denoising(monkeypatch) -> None:
    calls: list[tuple] = []

    def _track_denoise(gray, h=10, templateWindowSize=7, searchWindowSize=21):
        calls.append((h, templateWindowSize, searchWindowSize))
        return gray

    monkeypatch.setattr(
        ocr_service.pytesseract,
        "image_to_osd",
        lambda _gray, config="": "Rotate: 0\n",
    )
    monkeypatch.setattr(cv2, "fastNlMeansDenoising", _track_denoise)

    img = np.full((30, 60, 3), 255, dtype=np.uint8)
    _, encoded = cv2.imencode(".png", img)
    preprocess_image_for_ocr(encoded.tobytes())
    assert calls == [(10, 7, 21)]


def test_medical_overview_coerces_legacy_medication_strings() -> None:
    overview = MedicalOverview.model_validate(
        {
            "current_medications": ["متفورمین", "لوزارتان"],
        }
    )
    assert len(overview.current_medications) == 2
    assert overview.current_medications[0].name == "متفورمین"
    assert overview.current_medications[0].amount == ""
    assert overview.current_medications[0].frequency == ""
    assert overview.current_medications[0].id


def test_validate_file_link_id_accepts_medication_id() -> None:
    med_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    overview = MedicalOverview(
        current_medications=[
            CurrentMedication(id=med_id, name="متفورمین", amount="۱ عدد", frequency="هر ۲۴ ساعت"),
        ]
    )
    assert validate_file_link_id(overview, med_id) is True


def test_format_medication_for_summary_with_dosage() -> None:
    medication = CurrentMedication(
        id="med-1",
        name="متفورمین",
        amount="۱ عدد",
        frequency="هر ۲۴ ساعت",
    )
    assert format_medication_for_summary(medication) == "متفورمین - ۱ عدد هر ۲۴ ساعت"


def test_format_medication_for_summary_unknown_with_file() -> None:
    medication = CurrentMedication(id="med-1", name="", amount="", frequency="")
    assert (
        format_medication_for_summary(medication, has_file=True)
        == "نامشخص - تصویر پیوست شد"
    )
