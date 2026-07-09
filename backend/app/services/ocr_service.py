import logging
import re

import cv2
import numpy as np
import pytesseract

logger = logging.getLogger(__name__)

LAB_VALUE_RE = re.compile(
    r"(?i)\b(WBC|RBC|HGB|Hb|MCHC|MCH|Platelets?|PLT)\b"
    r"[\s:.\-–—|]*"
    r"([\d,]+(?:\.\d+)?)",
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


def preprocess_image_for_ocr(image_bytes: bytes) -> np.ndarray:
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image bytes")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
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


def _run_tesseract(processed: np.ndarray) -> str:
    texts: list[str] = []
    for psm in (6, 11):
        text = pytesseract.image_to_string(
            processed,
            lang="eng+fas",
            config=f"--psm {psm}",
        )
        if text.strip():
            texts.append(text)
    return "\n".join(texts)


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


def extract_medication_ocr(file_bytes: bytes, mime_type: str) -> str | None:
    # TODO: Implement Tesseract OCR matched against Iranian FDA drug dictionary.
    _ = file_bytes, mime_type
    return None


def extract_lab_values_ocr(image_bytes: bytes) -> str | None:
    try:
        processed = preprocess_image_for_ocr(image_bytes)
        raw_text = _run_tesseract(processed)
        pairs = _extract_lab_pairs(raw_text)
        if not pairs:
            return None
        return ", ".join(f"{key}: {value}" for key, value in pairs.items())
    except Exception:
        logger.exception("Lab OCR pipeline failed")
        return None
