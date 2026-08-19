"""Document OCR with page/word-level provenance.

This module owns the ``DOCUMENT → RAW OCR RESULT`` stage. It is deliberately
"dumb": it transcribes, it never interprets. Clinical meaning is assigned later
by :mod:`app.services.document_extraction`.

Provenance contract
-------------------
Every transcribed token keeps the facts needed to trace a clinical value back to
its source: page number, bounding box (when the engine provides one), the exact
source text, and the engine's confidence.

Degradation contract
--------------------
When an engine is unavailable (no Tesseract binary, no Poppler for PDF
rasterisation) or a file is unreadable, this module raises
:class:`DocumentOcrUnavailable` / :class:`DocumentOcrFailed`. It never returns
fabricated text, and callers must record the failure rather than substitute a
guess.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Sequence

import cv2
import numpy as np
import pytesseract
from loguru import logger

from app.services.file_processor import file_processor

#: Engine identifiers persisted on DocumentArtifact.engine.
ENGINE_PDF_TEXT_LAYER = "pypdf-text-layer"
ENGINE_TESSERACT = "tesseract"

#: Tesseract language pack used for Persian + English medical documents.
TESSERACT_LANGS = "eng+fas"

#: Page segmentation modes tried per image; the higher-confidence run wins.
_PSM_CANDIDATES = (6, 11)

_OSD_ROTATE_RE = re.compile(r"Rotate:\s*(\d+)", re.IGNORECASE)

#: Below this mean confidence the transcription is flagged for human review
#: instead of being trusted as a clinical value source.
LOW_CONFIDENCE_THRESHOLD = 0.60

#: Cap rasterised PDF pages so a large upload cannot pin a worker indefinitely.
MAX_PDF_RASTER_PAGES = 20


class DocumentOcrError(Exception):
    """Base class for document OCR failures."""


class DocumentOcrUnavailable(DocumentOcrError):
    """A required OCR engine or system dependency is not installed."""


class DocumentOcrFailed(DocumentOcrError):
    """The document could not be transcribed (unreadable / decode failure)."""


@dataclass(frozen=True)
class OcrWord:
    """A single transcribed token with its provenance."""

    text: str
    #: Engine confidence normalised to [0.0, 1.0]; None when not reported.
    confidence: float | None
    page: int
    #: (left, top, width, height) in pixels of the rendered page; None when the
    #: engine has no geometry (e.g. a PDF text layer).
    bbox: tuple[int, int, int, int] | None
    line: int = 0
    block: int = 0


@dataclass(frozen=True)
class OcrLine:
    """Words grouped into a source line — the unit clinical parsing works on."""

    page: int
    text: str
    words: tuple[OcrWord, ...]

    @property
    def bbox(self) -> tuple[int, int, int, int] | None:
        """Union of the member word boxes, or None when no word has geometry."""
        boxes = [w.bbox for w in self.words if w.bbox is not None]
        if not boxes:
            return None
        left = min(b[0] for b in boxes)
        top = min(b[1] for b in boxes)
        right = max(b[0] + b[2] for b in boxes)
        bottom = max(b[1] + b[3] for b in boxes)
        return (left, top, right - left, bottom - top)

    @property
    def confidence(self) -> float | None:
        scored = [w.confidence for w in self.words if w.confidence is not None]
        if not scored:
            return None
        return sum(scored) / len(scored)


@dataclass(frozen=True)
class OcrPage:
    """One transcribed page."""

    page_number: int
    text: str
    lines: tuple[OcrLine, ...] = ()

    @property
    def confidence(self) -> float | None:
        scored = [line.confidence for line in self.lines if line.confidence is not None]
        if not scored:
            return None
        return sum(scored) / len(scored)


@dataclass(frozen=True)
class OcrDocument:
    """Full transcription result for one uploaded file."""

    engine: str
    engine_version: str
    pages: tuple[OcrPage, ...] = field(default_factory=tuple)

    @property
    def text(self) -> str:
        return "\n".join(page.text for page in self.pages if page.text).strip()

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def confidence(self) -> float | None:
        scored = [p.confidence for p in self.pages if p.confidence is not None]
        if not scored:
            return None
        return sum(scored) / len(scored)

    @property
    def lines(self) -> tuple[OcrLine, ...]:
        return tuple(line for page in self.pages for line in page.lines)

    @property
    def needs_review(self) -> bool:
        """True when the transcription is too weak to trust as a value source."""
        confidence = self.confidence
        if confidence is None:
            # A text layer reports no confidence; absence is not low confidence.
            return False
        return confidence < LOW_CONFIDENCE_THRESHOLD


# ---------------------------------------------------------------------------
# Engine capability probes (cheap, cached by the module import)
# ---------------------------------------------------------------------------


def tesseract_version() -> str | None:
    """Return the installed Tesseract version, or None when unavailable."""
    try:
        return str(pytesseract.get_tesseract_version())
    except Exception as exc:  # pragma: no cover - environment dependent
        logger.warning("Tesseract unavailable: {}", exc)
        return None


def _pdf2image_convert():
    """Return ``pdf2image.convert_from_bytes`` or None when unusable."""
    try:
        from pdf2image import convert_from_bytes
    except Exception as exc:  # pragma: no cover - environment dependent
        logger.warning("pdf2image unavailable: {}", exc)
        return None
    return convert_from_bytes


# ---------------------------------------------------------------------------
# Image preprocessing
# ---------------------------------------------------------------------------


def _parse_osd_rotation(osd_text: str) -> int:
    match = _OSD_ROTATE_RE.search(osd_text)
    if not match:
        return 0
    angle = int(match.group(1)) % 360
    return angle if angle in (0, 90, 180, 270) else 0


def _correct_orientation(img: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    try:
        rotation = _parse_osd_rotation(pytesseract.image_to_osd(gray, config="--psm 0"))
    except Exception as exc:
        logger.debug("OSD orientation detection skipped: {}", exc)
        return img

    if rotation == 90:
        return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    if rotation == 180:
        return cv2.rotate(img, cv2.ROTATE_180)
    if rotation == 270:
        return cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return img


def preprocess_for_ocr(img: np.ndarray) -> np.ndarray:
    """Deskew/denoise/binarise a BGR image for Tesseract."""
    img = _correct_orientation(img)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    denoised = cv2.fastNlMeansDenoising(
        gray, h=10, templateWindowSize=7, searchWindowSize=21
    )
    blurred = cv2.GaussianBlur(denoised, (3, 3), 0)
    thresholded = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    return cv2.dilate(thresholded, kernel, iterations=1)


def _decode_image(image_bytes: bytes) -> np.ndarray:
    array = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if img is None:
        raise DocumentOcrFailed("Could not decode image bytes")
    return img


# ---------------------------------------------------------------------------
# Tesseract → OcrPage
# ---------------------------------------------------------------------------


def _words_from_tsv(data: dict, page_number: int) -> list[OcrWord]:
    words: list[OcrWord] = []
    texts = data.get("text", []) or []
    confs = data.get("conf", []) or []
    lefts = data.get("left", []) or []
    tops = data.get("top", []) or []
    widths = data.get("width", []) or []
    heights = data.get("height", []) or []
    lines = data.get("line_num", []) or []
    blocks = data.get("block_num", []) or []
    pars = data.get("par_num", []) or []

    for idx, raw_text in enumerate(texts):
        text = str(raw_text).strip()
        if not text:
            continue

        try:
            conf_value = float(confs[idx])
        except (IndexError, TypeError, ValueError):
            conf_value = -1.0
        confidence = conf_value / 100.0 if conf_value >= 0 else None

        try:
            bbox = (
                int(lefts[idx]),
                int(tops[idx]),
                int(widths[idx]),
                int(heights[idx]),
            )
        except (IndexError, TypeError, ValueError):
            bbox = None

        def _at(seq: Sequence, default: int = 0) -> int:
            try:
                return int(seq[idx])
            except (IndexError, TypeError, ValueError):
                return default

        # Distinguish lines across blocks/paragraphs so two columns do not merge.
        block = _at(blocks)
        composite_line = (block, _at(pars), _at(lines))
        words.append(
            OcrWord(
                text=text,
                confidence=confidence,
                page=page_number,
                bbox=bbox,
                line=hash(composite_line) & 0x7FFFFFFF,
                block=block,
            )
        )
    return words


def _group_lines(words: list[OcrWord], page_number: int) -> tuple[OcrLine, ...]:
    ordered: dict[int, list[OcrWord]] = {}
    order: list[int] = []
    for word in words:
        if word.line not in ordered:
            ordered[word.line] = []
            order.append(word.line)
        ordered[word.line].append(word)

    lines: list[OcrLine] = []
    for key in order:
        members = ordered[key]
        text = " ".join(w.text for w in members).strip()
        if not text:
            continue
        lines.append(
            OcrLine(page=page_number, text=text, words=tuple(members))
        )
    return tuple(lines)


def _ocr_image_page(img: np.ndarray, page_number: int) -> OcrPage:
    """Transcribe one page image, keeping the highest-confidence PSM result."""
    processed = preprocess_for_ocr(img)

    best_page: OcrPage | None = None
    best_score = -1.0

    for psm in _PSM_CANDIDATES:
        config = f"--psm {psm}"
        try:
            data = pytesseract.image_to_data(
                processed,
                lang=TESSERACT_LANGS,
                config=config,
                output_type=pytesseract.Output.DICT,
            )
        except pytesseract.TesseractNotFoundError as exc:
            raise DocumentOcrUnavailable("Tesseract binary is not installed") from exc
        except Exception as exc:
            logger.warning("Tesseract psm={} failed: {}", psm, exc)
            continue

        words = _words_from_tsv(data, page_number)
        if not words:
            continue
        lines = _group_lines(words, page_number)
        page = OcrPage(
            page_number=page_number,
            text="\n".join(line.text for line in lines),
            lines=lines,
        )
        # Rank by confidence, breaking ties toward the transcription that
        # recovered more text (a sparse high-confidence run loses real content).
        score = (page.confidence or 0.0) * 1000 + len(page.text)
        if score > best_score:
            best_score = score
            best_page = page

    if best_page is None:
        return OcrPage(page_number=page_number, text="", lines=())
    return best_page


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def _ocr_pdf_text_layer(file_bytes: bytes) -> OcrDocument | None:
    """Read an embedded PDF text layer. Returns None when there is none."""
    text = file_processor.extract_text_from_pdf(file_bytes)
    if not text or text.startswith("خطا در خواندن PDF"):
        return None
    text = text.strip()
    if not text:
        return None

    # ``extract_text_from_pdf`` joins pages with a trailing newline per page; keep
    # page boundaries so provenance can cite a page number.
    raw_pages = [chunk.strip() for chunk in text.split("\n\n") if chunk.strip()]
    if len(raw_pages) <= 1:
        raw_pages = [text]

    pages: list[OcrPage] = []
    for index, page_text in enumerate(raw_pages, start=1):
        lines = tuple(
            OcrLine(
                page=index,
                text=line.strip(),
                words=(
                    OcrWord(
                        text=line.strip(),
                        confidence=None,
                        page=index,
                        bbox=None,
                    ),
                ),
            )
            for line in page_text.splitlines()
            if line.strip()
        )
        pages.append(OcrPage(page_number=index, text=page_text, lines=lines))

    return OcrDocument(
        engine=ENGINE_PDF_TEXT_LAYER,
        engine_version="pypdf",
        pages=tuple(pages),
    )


def _ocr_pdf_rasterised(file_bytes: bytes, version: str) -> OcrDocument:
    convert = _pdf2image_convert()
    if convert is None:
        raise DocumentOcrUnavailable(
            "Scanned PDF requires pdf2image + Poppler, which are not available"
        )

    try:
        images = convert(file_bytes, dpi=300)
    except Exception as exc:
        raise DocumentOcrUnavailable(
            f"PDF rasterisation failed: {type(exc).__name__}"
        ) from exc

    if not images:
        raise DocumentOcrFailed("PDF contained no rasterisable pages")

    pages: list[OcrPage] = []
    for index, pil_image in enumerate(images[:MAX_PDF_RASTER_PAGES], start=1):
        bgr = cv2.cvtColor(np.array(pil_image.convert("RGB")), cv2.COLOR_RGB2BGR)
        pages.append(_ocr_image_page(bgr, index))

    if len(images) > MAX_PDF_RASTER_PAGES:
        logger.warning(
            "PDF truncated for OCR: transcribed {}/{} pages (MAX_PDF_RASTER_PAGES)",
            MAX_PDF_RASTER_PAGES,
            len(images),
        )

    return OcrDocument(
        engine=ENGINE_TESSERACT,
        engine_version=version,
        pages=tuple(pages),
    )


def is_ocr_supported(mime_type: str) -> bool:
    """True when this MIME type has a transcription path."""
    normalized = (mime_type or "").lower()
    return normalized == "application/pdf" or normalized.startswith("image/")


def run_document_ocr(file_bytes: bytes, mime_type: str) -> OcrDocument:
    """Transcribe an uploaded document.

    Raises
    ------
    DocumentOcrUnavailable
        A needed engine/system dependency is missing.
    DocumentOcrFailed
        The document is unreadable or unsupported.
    """
    normalized = (mime_type or "").lower()

    if normalized == "application/pdf":
        text_layer = _ocr_pdf_text_layer(file_bytes)
        if text_layer is not None:
            return text_layer
        version = tesseract_version()
        if version is None:
            raise DocumentOcrUnavailable(
                "Scanned PDF requires Tesseract, which is not installed"
            )
        return _ocr_pdf_rasterised(file_bytes, version)

    if normalized.startswith("image/"):
        version = tesseract_version()
        if version is None:
            raise DocumentOcrUnavailable("Tesseract binary is not installed")
        page = _ocr_image_page(_decode_image(file_bytes), 1)
        return OcrDocument(
            engine=ENGINE_TESSERACT,
            engine_version=version,
            pages=(page,),
        )

    raise DocumentOcrFailed(f"Unsupported MIME type for OCR: {mime_type!r}")
