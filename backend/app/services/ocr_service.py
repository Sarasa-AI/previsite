import re
from dataclasses import dataclass, field

import cv2
import numpy as np
import pytesseract
from loguru import logger

from app.core.observability.stages import PipelineModule, PipelineStage
from app.core.observability.timing import pipeline_stage_sync
from app.modules.medications.application.resolver import MedicationResolver
from app.modules.medications.domain.models import (
    Medication,
    MedicationPrescription,
    MedicationProvenance,
    MedicationSource,
    ResolvedMedication,
)
from app.modules.medications.infrastructure.catalog import CatalogUnavailableError
from app.services.file_processor import file_processor

LAB_VALUE_RE = re.compile(
    r"(?i)\b(WBC|RBC|HGB|Hb|MCHC|MCH|Platelets?|PLT)\b"
    r"[\s:.\-–—|]*"
    r"([\d,]+(?:\.\d+)?)",
)

CGM_VALUE_TIME_RE = re.compile(
    r"(?P<value>\d{2,3})\s*[-–—:|]+\s*(?P<time>\d{1,2}:\d{2})",
)
CGM_TIME_VALUE_RE = re.compile(
    r"(?P<time>\d{1,2}:\d{2})\s*[-–—:|]+\s*(?P<value>\d{2,3})",
)

_KEY_ALIASES: dict[str, str] = {
    "wbc": "WBC",
    "rbc": "RBC",
    "hgb": "Hb",
    "hb": "Hb",
    "mchc": "MCHC",
    "mch": "MCH",
    "platelet": "Platelet",
    "platelets": "Platelet",
    "plt": "Platelet",
}

_NOISE_LINE_RE = re.compile(r"^[\d\s:.\-–—|,]+$")
_OSD_ROTATE_RE = re.compile(r"Rotate:\s*(\d+)", re.IGNORECASE)
_HANDWRITING_CONFIDENCE_THRESHOLD = 60
_MIN_CGM_READINGS = 2
OCR_MEDICATION_CANDIDATE_LIMIT = 3

# --- Conservative prescription-phrase extraction (same block as the match) ---
#
# DrugYab catalog data carries no dose/frequency/duration/route/quantity and
# the OCR pipeline must not invent them. The patterns below only capture
# explicit, unambiguous prescription phrases that appear in the same OCR block
# as the matched drug name. Everything else stays None.

_PERSIAN_TO_ASCII_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
_ASCII_TO_PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
_PERSIAN_NUMBER_WORDS = {
    "یک": "۱",
    "دو": "۲",
    "سه": "۳",
    "چهار": "۴",
    "پنج": "۵",
    "شش": "۶",
    "هفت": "۷",
    "هشت": "۸",
    "نه": "۹",
    "نصف": "۰٫۵",
    "نیم": "۰٫۵",
}
_DISCRETE_DOSE_UNITS = ("قرص", "کپسول", "عدد", "قطره", "پاف", "آمپول")
_DOSE_UNITS = _DISCRETE_DOSE_UNITS + ("میلی‌لیتر", "میلی لیتر", "ساشه", "گرم")

_DOSE_PHRASE_RE = re.compile(
    r"(?:هر\s*بار\s*)?(?P<dose>یک|دو|سه|چهار|نصف|نیم|[\d۰-۹]+(?:[./٫][\d۰-۹]+)?)\s*"
    r"(?P<unit>" + "|".join(_DOSE_UNITS) + ")"
)
_FREQUENCY_DAILY_RE = re.compile(
    r"روزی\s*(?P<value>یک|دو|سه|چهار|پنج|شش|[\d۰-۹]+)\s*(?:بار|نوبت)"
)
_FREQUENCY_INTERVAL_RE = re.compile(r"هر\s*(?P<value>[\d۰-۹]+)\s*ساعت")
_INSTRUCTION_PHRASE_RE = re.compile(
    r"قبل از غذا|بعد از غذا|همراه با غذا|همراه غذا|ناشتا|قبل از خواب|در صورت نیاز|صبح و شب"
)


def _to_ascii_digits(value: str) -> str:
    return value.translate(_PERSIAN_TO_ASCII_DIGITS)


def _to_persian_number(value: str) -> str:
    word = _PERSIAN_NUMBER_WORDS.get(value.strip())
    if word:
        return word
    return value.strip().translate(_ASCII_TO_PERSIAN_DIGITS)


def _extract_prescription_instructions(text: str) -> dict[str, str]:
    """Conservatively extract explicit prescription phrases from OCR text.

    Only unambiguous phrases are captured; anything uncertain stays absent so
    the caller keeps the field None. quantity, duration and
    route are never inferred here.
    """

    extracted: dict[str, str] = {}

    frequency_match = _FREQUENCY_DAILY_RE.search(text) or _FREQUENCY_INTERVAL_RE.search(text)
    if frequency_match:
        if _FREQUENCY_DAILY_RE.search(text):
            match = _FREQUENCY_DAILY_RE.search(text)
            extracted["frequency"] = f"روزی {_to_persian_number(match.group('value'))} بار"
        else:
            match = _FREQUENCY_INTERVAL_RE.search(text)
            extracted["frequency"] = f"هر {_to_persian_number(match.group('value'))} ساعت"

    instruction_match = _INSTRUCTION_PHRASE_RE.search(text)
    if instruction_match:
        extracted["instructions"] = instruction_match.group(0)

    for dose_match in _DOSE_PHRASE_RE.finditer(text):
        raw_dose = dose_match.group("dose")
        unit = dose_match.group("unit").replace("میلی لیتر", "میلی‌لیتر")
        prefixed = dose_match.group(0).startswith("هر بار")
        numeric = _to_ascii_digits(raw_dose)
        if unit in _DISCRETE_DOSE_UNITS:
            if (
                raw_dose not in ("نصف", "نیم")
                and not prefixed
                and numeric.isdigit()
                and int(numeric) > 10
            ):
                continue
        elif not prefixed:
            # Grams/ml/sachets without an explicit "هر بار" phrase are too
            # ambiguous (product size vs dose) to record as prescription dose.
            continue
        extracted["dose"] = _to_persian_number(raw_dose)
        extracted["dose_unit"] = unit
        break

    return extracted


def _strip_prescription_phrases(text: str) -> str:
    """Remove explicit prescription phrases so a block can re-match by drug name."""

    stripped = _FREQUENCY_DAILY_RE.sub(" ", text)
    stripped = _FREQUENCY_INTERVAL_RE.sub(" ", stripped)
    stripped = _INSTRUCTION_PHRASE_RE.sub(" ", stripped)
    stripped = _DOSE_PHRASE_RE.sub(" ", stripped)
    return re.sub(r"\s+", " ", stripped).strip()


def _candidate_payload(medication: ResolvedMedication) -> dict[str, object]:
    return {
        "catalog_id": medication.id,
        "name": medication.display_name,
        "generic_name": medication.generic_name_en,
        "strength": medication.strength,
        "form": medication.form,
        "manufacturer": medication.manufacturer,
        "company": medication.company_name,
        "dose_unit": medication.dose_unit,
        "catalog": medication.catalog.model_dump() if medication.catalog else None,
    }


@dataclass
class TesseractMeta:
    avg_confidence: float = 0.0
    block_word_counts: list[int] = field(default_factory=list)
    non_alnum_ratio: float = 0.0


@dataclass(frozen=True)
class CgmReading:
    value: str
    time: str


def _parse_osd_rotation(osd_text: str) -> int:
    match = _OSD_ROTATE_RE.search(osd_text)
    if not match:
        return 0
    angle = int(match.group(1)) % 360
    return angle if angle in (0, 90, 180, 270) else 0


def _correct_image_orientation(img: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    try:
        osd_text = pytesseract.image_to_osd(gray, config="--psm 0")
        rotation = _parse_osd_rotation(osd_text)
    except Exception as exc:
        logger.warning("OSD orientation detection failed: {}", exc)
        return img

    if rotation == 0:
        return img
    if rotation == 90:
        return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    if rotation == 180:
        return cv2.rotate(img, cv2.ROTATE_180)
    if rotation == 270:
        return cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return img


def preprocess_image_for_ocr(image_bytes: bytes) -> np.ndarray:
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image bytes")

    img = _correct_image_orientation(img)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    denoised = cv2.fastNlMeansDenoising(gray, h=10, templateWindowSize=7, searchWindowSize=21)
    blurred = cv2.GaussianBlur(denoised, (3, 3), 0)
    thresholded = cv2.adaptiveThreshold(
        blurred,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        11,
        2,
    )
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    return cv2.dilate(thresholded, kernel, iterations=1)


def _extract_pdf_text(file_bytes: bytes) -> str | None:
    text = file_processor.extract_text_from_pdf(file_bytes)
    if not text or text.startswith("خطا در خواندن PDF"):
        return None
    return text.strip() or None


def _build_tesseract_meta(data: dict, raw_text: str) -> TesseractMeta:
    confidences: list[float] = []
    block_words: dict[int, int] = {}

    for conf, block_num, text in zip(
        data.get("conf", []),
        data.get("block_num", []),
        data.get("text", []),
    ):
        word = str(text).strip()
        if not word:
            continue
        try:
            conf_value = float(conf)
        except (TypeError, ValueError):
            continue
        if conf_value < 0:
            continue
        confidences.append(conf_value)
        block_words[block_num] = block_words.get(block_num, 0) + 1

    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    non_alnum = sum(1 for ch in raw_text if not ch.isalnum() and not ch.isspace())
    non_alnum_ratio = non_alnum / len(raw_text) if raw_text else 0.0

    return TesseractMeta(
        avg_confidence=avg_confidence,
        block_word_counts=list(block_words.values()),
        non_alnum_ratio=non_alnum_ratio,
    )


def _run_tesseract_with_meta(processed: np.ndarray) -> tuple[str, TesseractMeta]:
    texts: list[str] = []
    meta = TesseractMeta()

    for psm in (6, 11):
        text = pytesseract.image_to_string(
            processed,
            lang="eng+fas",
            config=f"--psm {psm}",
        )
        if text.strip():
            texts.append(text)

        data = pytesseract.image_to_data(
            processed,
            lang="eng+fas",
            config=f"--psm {psm}",
            output_type=pytesseract.Output.DICT,
        )
        psm_meta = _build_tesseract_meta(data, text)
        if psm_meta.avg_confidence > meta.avg_confidence:
            meta = psm_meta

    raw_text = "\n".join(texts)
    if not meta.avg_confidence and raw_text:
        meta = _build_tesseract_meta({"conf": [], "block_num": [], "text": []}, raw_text)
    return raw_text, meta


def _run_tesseract(processed: np.ndarray) -> str:
    raw_text, _meta = _run_tesseract_with_meta(processed)
    return raw_text


def _is_sparse_or_handwriting(meta: TesseractMeta, raw_text: str) -> bool:
    if meta.avg_confidence and meta.avg_confidence < _HANDWRITING_CONFIDENCE_THRESHOLD:
        return True

    sparse_blocks = sum(1 for count in meta.block_word_counts if count <= 2)
    if sparse_blocks >= 3:
        return True

    if raw_text and meta.non_alnum_ratio > 0.45:
        return True

    return False


def _split_ocr_blocks(raw_text: str) -> list[str]:
    blocks: list[str] = []
    for line in raw_text.splitlines():
        candidate = line.strip()
        if len(candidate) < 2:
            continue
        if _NOISE_LINE_RE.fullmatch(candidate):
            continue
        blocks.append(candidate)
    return blocks


def _normalize_lab_key(raw_key: str) -> str:
    return _KEY_ALIASES.get(raw_key.lower(), raw_key)


def _extract_lab_pairs(ocr_text: str) -> dict[str, str]:
    pairs: dict[str, str] = {}
    for match in LAB_VALUE_RE.finditer(ocr_text):
        canonical = _normalize_lab_key(match.group(1))
        if canonical in pairs:
            continue
        value = match.group(2).replace(",", "")
        pairs[canonical] = value
    return pairs


def _extract_cgm_readings(ocr_text: str) -> list[CgmReading]:
    readings: list[CgmReading] = []
    seen: set[tuple[str, str]] = set()

    for pattern in (CGM_VALUE_TIME_RE, CGM_TIME_VALUE_RE):
        for match in pattern.finditer(ocr_text):
            value = match.group("value")
            time = match.group("time")
            key = (value, time)
            if key in seen:
                continue
            seen.add(key)
            readings.append(CgmReading(value=value, time=time))

    return readings


def _format_lab_output(pairs: dict[str, str]) -> str:
    return ", ".join(f"{key}: {value}" for key, value in pairs.items())


def _format_cgm_output(readings: list[CgmReading]) -> str:
    return "CGM: " + ", ".join(f"{reading.value} @ {reading.time}" for reading in readings)


def _vision_handwriting_todo(*, pipeline: str, reason: str) -> None:
    # TODO: Connect to a vision-based local model or cloud endpoint
    # specifically for medical handwriting/object localization.
    logger.warning(
        "OCR handwriting fallback triggered pipeline={} reason={}",
        pipeline,
        reason,
    )


def _parse_lab_text(
    raw_text: str,
    *,
    handwriting_likely: bool = False,
) -> str | None:
    cgm_readings = _extract_cgm_readings(raw_text)
    if len(cgm_readings) >= _MIN_CGM_READINGS:
        return _format_cgm_output(cgm_readings)

    pairs = _extract_lab_pairs(raw_text)
    if pairs:
        return _format_lab_output(pairs)

    if handwriting_likely and cgm_readings:
        _vision_handwriting_todo(
            pipeline="lab",
            reason="handwriting_likely_with_partial_cgm_readings",
        )
        return None

    if handwriting_likely:
        _vision_handwriting_todo(pipeline="lab", reason="handwriting_likely_no_lab_pairs")
        return None

    if raw_text.strip():
        logger.warning(
            "OCR lab extraction produced no matches pipeline=lab text_length={}",
            len(raw_text.strip()),
        )

    return None


def _medication_resolver() -> MedicationResolver:
    return MedicationResolver()


def _medication_ocr_item(
    medication: ResolvedMedication,
    *,
    prescription: MedicationPrescription | None = None,
    candidates: tuple[ResolvedMedication, ...] = (),
) -> dict[str, object]:
    """Build the canonical OCR medication payload without fabricated instructions."""

    if prescription is None:
        prescription = MedicationPrescription(dose_unit=medication.dose_unit)
    ambiguous = len(candidates) > 1
    composed = Medication.from_resolved(
        medication,
        prescription=prescription,
        provenance=MedicationProvenance(
            source=MedicationSource.OCR,
            verification_status="ambiguous" if ambiguous else "needs_review",
        ),
    )
    payload = composed.model_dump()
    payload["ambiguous"] = ambiguous
    payload["candidate_count"] = len(candidates) or 1
    payload["candidates"] = [_candidate_payload(candidate) for candidate in candidates]
    return payload


def _match_medications_from_text(
    raw_text: str,
    *,
    handwriting_likely: bool = False,
) -> list[dict[str, object]] | None:
    if not raw_text.strip():
        return None

    resolver = _medication_resolver()
    matched_medications: list[
        tuple[ResolvedMedication, MedicationPrescription | None, tuple[ResolvedMedication, ...]]
    ] = []
    seen_catalog_ids: set[int] = set()
    resolved_queries: set[str] = set()

    def _resolve_and_record(
        query: str,
        extracted: dict[str, str] | None = None,
    ) -> bool:
        if query in resolved_queries:
            return True
        resolved_queries.add(query)
        resolution = resolver.resolve_ocr(query, limit=OCR_MEDICATION_CANDIDATE_LIMIT)
        if not resolution.medications:
            return False
        medication = resolution.medications[0]
        if medication.id in seen_catalog_ids:
            return True
        seen_catalog_ids.add(medication.id)
        prescription = None
        if extracted:
            prescription = MedicationPrescription(
                dose=extracted.get("dose"),
                dose_unit=extracted.get("dose_unit") or medication.dose_unit,
                frequency=extracted.get("frequency"),
                instructions=extracted.get("instructions"),
            )
        matched_medications.append((medication, prescription, resolution.medications))
        return True

    blocks = _split_ocr_blocks(raw_text)
    force_blocks = handwriting_likely or len(blocks) >= 2

    if not force_blocks:
        prescription = _extract_prescription_instructions(raw_text)
        if not _resolve_and_record(raw_text, prescription):
            stripped = _strip_prescription_phrases(raw_text)
            if stripped and stripped != raw_text:
                _resolve_and_record(stripped, prescription)
        if matched_medications:
            medication, prescription, candidates = matched_medications[0]
            return [_medication_ocr_item(medication, prescription=prescription, candidates=candidates)]

    for block in blocks:
        prescription = _extract_prescription_instructions(block)
        if not _resolve_and_record(block, prescription):
            stripped = _strip_prescription_phrases(block)
            if stripped and stripped != block:
                _resolve_and_record(stripped, prescription)

    # A single-product label often carries instructions on their own lines
    # (e.g. Persian instructions below an English brand name). Block-scoped
    # extraction above cannot see phrases outside each line, so when every
    # matched product is the same drug and none captured instructions, attach
    # the phrases extracted from the full text. The rule only fires when all
    # matched products share one generic, so instructions are never
    # cross-associated between different drugs.
    if matched_medications and all(
        prescription is None for _, prescription, _ in matched_medications
    ):
        generics = {medication.generic_name_en for medication, _, _ in matched_medications}
        if len(generics) == 1 and next(iter(generics)):
            full_text_prescription = _extract_prescription_instructions(raw_text)
            if full_text_prescription:

                def _attach_full_text_prescription(
                    medication: ResolvedMedication,
                    candidates: tuple[ResolvedMedication, ...],
                ) -> tuple[ResolvedMedication, MedicationPrescription | None, tuple[ResolvedMedication, ...]]:
                    return (
                        medication,
                        MedicationPrescription(
                            dose=full_text_prescription.get("dose"),
                            dose_unit=full_text_prescription.get("dose_unit")
                            or medication.dose_unit,
                            frequency=full_text_prescription.get("frequency"),
                            instructions=full_text_prescription.get("instructions"),
                        ),
                        candidates,
                    )

                matched_medications = [
                    _attach_full_text_prescription(medication, candidates)
                    for medication, _, candidates in matched_medications
                ]

    if matched_medications:
        return [
            _medication_ocr_item(
                medication,
                prescription=prescription,
                candidates=candidates,
            )
            for medication, prescription, candidates in matched_medications
        ]

    if handwriting_likely:
        _vision_handwriting_todo(
            pipeline="medication",
            reason="handwriting_likely_no_drug_matches",
        )
    elif raw_text.strip():
        logger.warning(
            "OCR medication extraction produced no matches pipeline=medication text_length={}",
            len(raw_text.strip()),
        )

    return None


def _route_lab_extraction_from_text(
    raw_text: str,
    *,
    handwriting_likely: bool = False,
) -> str | None:
    if not raw_text.strip():
        return None
    return _parse_lab_text(raw_text, handwriting_likely=handwriting_likely)


def _route_lab_extraction(file_bytes: bytes, mime_type: str) -> str | None:
    if mime_type == "application/pdf":
        pdf_text = _extract_pdf_text(file_bytes)
        if pdf_text:
            return _route_lab_extraction_from_text(pdf_text, handwriting_likely=False)

        logger.warning(
            "OCR lab PDF text extraction failed; falling back to image OCR mime_type={}",
            mime_type,
        )
        try:
            processed = preprocess_image_for_ocr(file_bytes)
        except ValueError:
            return None
        raw_text, meta = _run_tesseract_with_meta(processed)
        if not raw_text.strip():
            logger.warning(
                "OCR lab pipeline returned empty text after Tesseract mime_type={}",
                mime_type,
            )
            return None
        return _route_lab_extraction_from_text(
            raw_text,
            handwriting_likely=_is_sparse_or_handwriting(meta, raw_text),
        )

    processed = preprocess_image_for_ocr(file_bytes)
    raw_text, meta = _run_tesseract_with_meta(processed)
    if not raw_text.strip():
        logger.warning(
            "OCR lab pipeline returned empty text after Tesseract mime_type={}",
            mime_type,
        )
        return None
    return _route_lab_extraction_from_text(
        raw_text,
        handwriting_likely=_is_sparse_or_handwriting(meta, raw_text),
    )


def _route_medication_extraction(file_bytes: bytes, mime_type: str) -> list[dict[str, object]] | None:
    _ = mime_type
    processed = preprocess_image_for_ocr(file_bytes)
    raw_text, meta = _run_tesseract_with_meta(processed)
    if not raw_text.strip():
        logger.warning(
            "OCR medication pipeline returned empty text after Tesseract mime_type={}",
            mime_type,
        )
        return None

    return _match_medications_from_text(
        raw_text,
        handwriting_likely=_is_sparse_or_handwriting(meta, raw_text),
    )


def extract_medication_ocr(file_bytes: bytes, mime_type: str) -> list[dict[str, object]] | None:
    if not mime_type.startswith("image/"):
        return None
    try:
        with pipeline_stage_sync(
            PipelineStage.OCR_EXTRACT,
            module=PipelineModule.OCR,
            ocr_type="medication",
            recoverable_on_error=True,
            retryable_on_error=True,
        ):
            return _route_medication_extraction(file_bytes, mime_type)
    except CatalogUnavailableError as exc:
        logger.warning(
            "Medication OCR resolution unavailable mime_type={} pipeline=medication "
            "resolution_status=unavailable error={}",
            mime_type,
            exc,
        )
        return None
    except Exception:
        logger.exception(
            "Medication OCR pipeline failed mime_type={} pipeline=medication",
            mime_type,
        )
        return None


def extract_lab_values_ocr(file_bytes: bytes, mime_type: str = "image/png") -> str | None:
    try:
        with pipeline_stage_sync(
            PipelineStage.OCR_EXTRACT,
            module=PipelineModule.OCR,
            ocr_type="lab",
            recoverable_on_error=True,
            retryable_on_error=True,
        ):
            if mime_type == "application/pdf" or mime_type.startswith("image/"):
                return _route_lab_extraction(file_bytes, mime_type)
            return None
    except Exception:
        logger.exception(
            "Lab OCR pipeline failed mime_type={} pipeline=lab",
            mime_type,
        )
        return None
