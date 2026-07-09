from app.services.medical_overview_service import (
    format_medication_for_summary,
    validate_file_link_id,
)
from app.services import ocr_service
from app.services.ocr_service import (
    _extract_lab_pairs,
    extract_lab_values_ocr,
    extract_medication_ocr,
    preprocess_image_for_ocr,
)
from app.schemas.intake import CurrentMedication, MedicalOverview
import cv2
import numpy as np


def test_extract_medication_ocr_stub_returns_none() -> None:
    assert extract_medication_ocr(b"fake-image", "image/png") is None


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

    def _fake_tesseract(_processed: np.ndarray) -> str:
        return sample_text

    monkeypatch.setattr(ocr_service, "_run_tesseract", _fake_tesseract)

    img = np.zeros((40, 200, 3), dtype=np.uint8)
    _, encoded = cv2.imencode(".png", img)
    result = extract_lab_values_ocr(encoded.tobytes())
    assert result == "WBC: 4.5, Hb: 13.2, Platelet: 150000"


def test_extract_lab_values_ocr_no_matches(monkeypatch) -> None:
    monkeypatch.setattr(ocr_service, "_run_tesseract", lambda _processed: "Patient Name: John Doe")

    img = np.zeros((40, 200, 3), dtype=np.uint8)
    _, encoded = cv2.imencode(".png", img)
    assert extract_lab_values_ocr(encoded.tobytes()) is None


def test_extract_lab_values_ocr_invalid_bytes() -> None:
    assert extract_lab_values_ocr(b"not-an-image") is None


def test_preprocess_image_for_ocr_returns_binary_matrix() -> None:
    img = np.full((30, 60, 3), 255, dtype=np.uint8)
    _, encoded = cv2.imencode(".png", img)
    processed = preprocess_image_for_ocr(encoded.tobytes())
    assert processed.ndim == 2
    assert processed.dtype == np.uint8
    assert processed.shape[0] > 0 and processed.shape[1] > 0


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
