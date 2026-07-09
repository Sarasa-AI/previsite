import re
from dataclasses import dataclass, field

import cv2
import numpy as np
import pytesseract
from loguru import logger

from app.services.drug_matcher import drug_matcher
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
DEFAULT_MEDICATION_AMOUNT = "۱ عدد"
DEFAULT_MEDICATION_FREQUENCY = "روزی ۱ بار"


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


def _medication_ocr_item(generic_name: str) -> dict[str, str]:
    return {
        "name": generic_name,
        "amount": DEFAULT_MEDICATION_AMOUNT,
        "frequency": DEFAULT_MEDICATION_FREQUENCY,
    }


def _match_medications_from_text(
    raw_text: str,
    *,
    handwriting_likely: bool = False,
) -> list[dict[str, str]] | None:
    if not raw_text.strip():
        return None

    matched_names: list[str] = []
    seen_generics: set[str] = set()

    def _record_match(match: dict | None) -> None:
        if match is None:
            return
        generic_name = match["generic_name"]
        if generic_name in seen_generics:
            return
        seen_generics.add(generic_name)
        matched_names.append(generic_name)

    blocks = _split_ocr_blocks(raw_text)
    force_blocks = handwriting_likely or len(blocks) >= 2

    if not force_blocks:
        _record_match(drug_matcher.match_drug(raw_text))
        if matched_names:
            return [_medication_ocr_item(matched_names[0])]

    for block in blocks:
        _record_match(drug_matcher.match_drug(block))

    if matched_names:
        return [_medication_ocr_item(name) for name in matched_names]

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


def _route_medication_extraction(file_bytes: bytes, mime_type: str) -> list[dict[str, str]] | None:
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


def extract_medication_ocr(file_bytes: bytes, mime_type: str) -> list[dict[str, str]] | None:
    if not mime_type.startswith("image/"):
        return None
    try:
        return _route_medication_extraction(file_bytes, mime_type)
    except Exception:
        logger.exception(
            "Medication OCR pipeline failed mime_type={} pipeline=medication",
            mime_type,
        )
        return None


def extract_lab_values_ocr(file_bytes: bytes, mime_type: str = "image/png") -> str | None:
    try:
        if mime_type == "application/pdf" or mime_type.startswith("image/"):
            return _route_lab_extraction(file_bytes, mime_type)
        return None
    except Exception:
        logger.exception(
            "Lab OCR pipeline failed mime_type={} pipeline=lab",
            mime_type,
        )
        return None
