from app.services.medical_overview_service import (
    format_medication_for_summary,
    validate_file_link_id,
)
from app.services import ocr_service
from app.modules.medications.application.resolver import MedicationResolver
from app.modules.medications.domain.models import CatalogMedication
from app.modules.medications.infrastructure.catalog import CatalogUnavailableError
from app.services.ocr_service import (
    TesseractMeta,
    _correct_image_orientation,
    _extract_cgm_readings,
    _extract_lab_pairs,
    _extract_prescription_instructions,
    extract_lab_values_ocr,
    extract_medication_ocr,
    preprocess_image_for_ocr,
)
from app.schemas.intake import CurrentMedication, MedicalOverview
import cv2
import numpy as np


def _mock_tesseract(text: str, meta: TesseractMeta | None = None):
    resolved_meta = meta or TesseractMeta(avg_confidence=90.0)
    return lambda _processed: (text, resolved_meta)


class RecordingOcrCatalog:
    def __init__(self, medications_by_query: dict[str, CatalogMedication]) -> None:
        self.medications_by_query = medications_by_query
        self.calls: list[tuple[str, int]] = []

    def search(self, query: str, limit: int = 20) -> tuple[CatalogMedication, ...]:
        self.calls.append((query, limit))
        medication = self.medications_by_query.get(query)
        return (medication,) if medication is not None and limit > 0 else ()


class MultiRecordingOcrCatalog:
    def __init__(self, medications_by_query: dict[str, tuple[CatalogMedication, ...]]) -> None:
        self.medications_by_query = medications_by_query

    def search(self, query: str, limit: int = 20) -> tuple[CatalogMedication, ...]:
        return self.medications_by_query.get(query, ())[:limit]


LOSARTAN = CatalogMedication(
    id=1,
    brand_name_fa="لوزارتان",
    brand_name_en="Losartan",
    generic_name_en="Losartan",
    form="TAB",
    strength="25 mg",
    manufacturer="Example",
)
METFORMIN = CatalogMedication(
    id=2,
    brand_name_fa="متفورمین",
    brand_name_en="Metformin",
    generic_name_en="Metformin",
    form="TAB",
    strength="500 mg",
    manufacturer="Example",
)


def _install_ocr_resolver(
    monkeypatch,
    medications_by_query: dict[str, CatalogMedication],
) -> RecordingOcrCatalog:
    catalog = RecordingOcrCatalog(medications_by_query)
    resolver = MedicationResolver(catalog)
    monkeypatch.setattr(ocr_service, "_medication_resolver", lambda: resolver)
    return catalog


def _expected_ocr_item(medication: CatalogMedication) -> dict[str, object]:
    """Expected canonical OCR medication payload for a TAB catalog row.

    OCR never fabricates dose/frequency; unknown prescription fields stay null
    and the record is marked for review rather than confirmed.
    """

    catalog_snapshot = {
        "catalog_id": medication.id,
        "brand_name": medication.brand_name_en,
        "brand_name_fa": medication.brand_name_fa,
        "brand_name_en": medication.brand_name_en,
        "generic_name": medication.generic_name_en,
        "generic_name_en": medication.generic_name_en,
        "generic_slug": None,
        "brand_slug": None,
        "strength_raw": medication.strength,
        "dosage_form": medication.form,
        "manufacturer": medication.manufacturer,
        "company_name": None,
        "company_slug": None,
    }

    return {
        "catalog_id": medication.id,
        "name": medication.brand_name_fa,
        "amount": "",
        "frequency": "",
        "dose_unit": "قرص",
        "catalog": catalog_snapshot,
        "prescription": {
            "dose": None,
            "dose_unit": "قرص",
            "quantity": None,
            "frequency": None,
            "duration": None,
            "route": None,
            "instructions": None,
        },
        "provenance": {
            "source": "ocr",
            "confidence": None,
            "verification_status": "needs_review",
        },
        "ambiguous": False,
        "candidate_count": 1,
        "candidates": [
            {
                "catalog_id": medication.id,
                "name": medication.brand_name_fa,
                "generic_name": medication.generic_name_en,
                "strength": medication.strength,
                "form": medication.form,
                "manufacturer": medication.manufacturer,
                "company": None,
                "dose_unit": "قرص",
                "catalog": catalog_snapshot,
            }
        ],
    }


def test_extract_medication_ocr_uses_shared_resolver_and_canonical_drug(monkeypatch) -> None:
    catalog = _install_ocr_resolver(monkeypatch, {"لوزارتان": LOSARTAN})
    monkeypatch.setattr(
        ocr_service,
        "_run_tesseract_with_meta",
        _mock_tesseract("لوزارتان"),
    )

    img = np.zeros((40, 200, 3), dtype=np.uint8)
    _, encoded = cv2.imencode(".png", img)
    result = extract_medication_ocr(encoded.tobytes(), "image/png")
    assert catalog.calls == [("لوزارتان", 3)]
    assert result == [_expected_ocr_item(LOSARTAN)]


def test_extract_medication_ocr_returns_none_when_no_match(monkeypatch) -> None:
    catalog = _install_ocr_resolver(monkeypatch, {})
    monkeypatch.setattr(
        ocr_service,
        "_run_tesseract_with_meta",
        _mock_tesseract("Patient Name: John Doe"),
    )

    img = np.zeros((40, 200, 3), dtype=np.uint8)
    _, encoded = cv2.imencode(".png", img)
    assert extract_medication_ocr(encoded.tobytes(), "image/png") is None
    assert catalog.calls == [("Patient Name: John Doe", 3)]


def test_extract_medication_ocr_invalid_bytes() -> None:
    assert extract_medication_ocr(b"not-an-image", "image/png") is None


def test_extract_medication_ocr_multi_drug_persian_list(monkeypatch) -> None:
    catalog = _install_ocr_resolver(
        monkeypatch,
        {"لوزارتان": LOSARTAN, "متفورمین": METFORMIN},
    )
    monkeypatch.setattr(
        ocr_service,
        "_run_tesseract_with_meta",
        _mock_tesseract("لوزارتان\nمتفورمین"),
    )

    img = np.zeros((40, 200, 3), dtype=np.uint8)
    _, encoded = cv2.imencode(".png", img)
    result = extract_medication_ocr(encoded.tobytes(), "image/png")
    assert catalog.calls == [("لوزارتان", 3), ("متفورمین", 3)]
    assert result == [_expected_ocr_item(LOSARTAN), _expected_ocr_item(METFORMIN)]


def test_extract_medication_ocr_partial_match_returns_matched_subset(monkeypatch) -> None:
    _install_ocr_resolver(monkeypatch, {"لوزارتان": LOSARTAN})
    monkeypatch.setattr(
        ocr_service,
        "_run_tesseract_with_meta",
        _mock_tesseract("لوزارتان\nنامشخص دارو"),
    )

    img = np.zeros((40, 200, 3), dtype=np.uint8)
    _, encoded = cv2.imencode(".png", img)
    result = extract_medication_ocr(encoded.tobytes(), "image/png")
    assert result == [_expected_ocr_item(LOSARTAN)]


def test_extract_medication_ocr_attaches_same_block_instructions(monkeypatch) -> None:
    _install_ocr_resolver(monkeypatch, {"لوزارتان": LOSARTAN})
    monkeypatch.setattr(
        ocr_service,
        "_run_tesseract_with_meta",
        _mock_tesseract("لوزارتان روزی دو بار بعد از غذا"),
    )

    img = np.zeros((40, 200, 3), dtype=np.uint8)
    _, encoded = cv2.imencode(".png", img)
    result = extract_medication_ocr(encoded.tobytes(), "image/png")
    assert result is not None
    item = result[0]
    assert item["catalog"]["catalog_id"] == LOSARTAN.id
    assert item["prescription"]["dose"] is None
    assert item["prescription"]["frequency"] == "روزی ۲ بار"
    assert item["prescription"]["instructions"] == "بعد از غذا"
    assert item["prescription"]["quantity"] is None
    assert item["provenance"]["verification_status"] == "needs_review"


def test_extract_medication_ocr_multi_line_label_preserves_instructions(monkeypatch) -> None:
    """Instructions on their own lines must survive block-split OCR labels.

    A real medication label lists the product on one line and instructions on
    the following lines (often in Persian). Block-scoped extraction would drop
    those phrases; when every matched product is the same drug, the full-text
    phrases are attached instead. Nothing is invented for fields the text
    does not mention.
    """

    persian_metformin = METFORMIN.model_copy(
        update={
            "id": 3,
            "brand_name_fa": "قرص آپو متفورمین 500 میلی گرم",
            "brand_name_en": "METFORMIN APO 500MG TAB",
        }
    )
    catalog = MultiRecordingOcrCatalog(
        {
            "Metformin 500 mg Tablets": (METFORMIN,),
            "متفورمین": (persian_metformin,),
        }
    )
    resolver = MedicationResolver(catalog)
    monkeypatch.setattr(ocr_service, "_medication_resolver", lambda: resolver)
    monkeypatch.setattr(
        ocr_service,
        "_run_tesseract_with_meta",
        _mock_tesseract(
            "METFORMIN\nMetformin 500 mg Tablets\nمتفورمین\n"
            "روزی ۲ بار\nبعد از غذا\nهر بار یک قرص"
        ),
    )

    img = np.zeros((40, 200, 3), dtype=np.uint8)
    _, encoded = cv2.imencode(".png", img)
    result = extract_medication_ocr(encoded.tobytes(), "image/png")
    assert result is not None
    assert len(result) == 2
    for item in result:
        assert item["prescription"]["dose"] == "۱"
        assert item["prescription"]["dose_unit"] == "قرص"
        assert item["prescription"]["frequency"] == "روزی ۲ بار"
        assert item["prescription"]["instructions"] == "بعد از غذا"
        assert item["prescription"]["quantity"] is None
        assert item["prescription"]["duration"] is None
        assert item["prescription"]["route"] is None


def test_extract_medication_ocr_multi_drug_label_never_cross_associates(
    monkeypatch,
) -> None:
    """Different drugs on one label must not share each other's instructions."""

    catalog = MultiRecordingOcrCatalog(
        {
            "Metformin 500 mg Tablets": (METFORMIN,),
            "لوزارتان": (LOSARTAN,),
        }
    )
    resolver = MedicationResolver(catalog)
    monkeypatch.setattr(ocr_service, "_medication_resolver", lambda: resolver)
    monkeypatch.setattr(
        ocr_service,
        "_run_tesseract_with_meta",
        _mock_tesseract(
            "Metformin 500 mg Tablets\nروزی ۲ بار\n"
            "لوزارتان\nبعد از غذا"
        ),
    )

    img = np.zeros((40, 200, 3), dtype=np.uint8)
    _, encoded = cv2.imencode(".png", img)
    result = extract_medication_ocr(encoded.tobytes(), "image/png")
    assert result is not None
    assert len(result) == 2
    for item in result:
        # Without a single shared generic, phrases must stay unassigned
        # rather than being attached to the wrong product.
        assert item["prescription"]["dose"] is None
        assert item["prescription"]["frequency"] is None
        assert item["prescription"]["instructions"] is None


def test_extract_medication_ocr_marks_ambiguous_candidates(monkeypatch) -> None:
    second = LOSARTAN.model_copy(
        update={"id": 11, "strength": "50 mg", "manufacturer": "Other"}
    )
    catalog = MultiRecordingOcrCatalog({"لوزارتان": (LOSARTAN, second)})
    resolver = MedicationResolver(catalog)
    monkeypatch.setattr(ocr_service, "_medication_resolver", lambda: resolver)
    monkeypatch.setattr(
        ocr_service,
        "_run_tesseract_with_meta",
        _mock_tesseract("لوزارتان"),
    )

    img = np.zeros((40, 200, 3), dtype=np.uint8)
    _, encoded = cv2.imencode(".png", img)
    result = extract_medication_ocr(encoded.tobytes(), "image/png")
    assert result is not None
    item = result[0]
    assert item["ambiguous"] is True
    assert item["candidate_count"] == 2
    assert item["provenance"]["verification_status"] == "ambiguous"
    assert len(item["candidates"]) == 2
    assert item["prescription"]["dose"] is None
    assert item["prescription"]["frequency"] is None


def test_handwriting_scenario_returns_none_with_no_match(monkeypatch) -> None:
    _install_ocr_resolver(monkeypatch, {})
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


def test_extract_medication_ocr_fails_safely_when_catalog_unavailable(
    monkeypatch,
    tmp_path,
) -> None:
    missing_catalog = tmp_path / "darooyab.db"
    warnings: list[tuple[str, tuple[object, ...]]] = []

    def _unavailable_resolver() -> MedicationResolver:
        raise CatalogUnavailableError(
            f"Darooyab catalog is unavailable at '{missing_catalog}'"
        )

    monkeypatch.setattr(ocr_service, "_medication_resolver", _unavailable_resolver)
    monkeypatch.setattr(
        ocr_service.logger,
        "warning",
        lambda message, *args: warnings.append((message, args)),
    )
    monkeypatch.setattr(
        ocr_service,
        "_run_tesseract_with_meta",
        _mock_tesseract("لوزارتان"),
    )

    img = np.zeros((40, 200, 3), dtype=np.uint8)
    _, encoded = cv2.imencode(".png", img)

    assert extract_medication_ocr(encoded.tobytes(), "image/png") is None
    assert any("resolution_status=unavailable" in message for message, _args in warnings)
    assert not missing_catalog.exists()


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
