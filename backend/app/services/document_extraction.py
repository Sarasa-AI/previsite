"""Deterministic clinical extraction from OCR output, with full provenance.

Owns the ``RAW OCR RESULT → STRUCTURED EXTRACTION`` stage.

Non-negotiable rules
--------------------
1. **Verbatim values.** A numeric value is copied character-for-character from the
   transcribed source. Nothing is rounded, rescaled, unit-converted, or inferred.
   If the page says ``Hb 11.2`` the artifact says ``11.2``.
2. **No invention.** Only analytes whose *name* is literally present next to a
   number are emitted. There are no defaults and no imputation.
3. **No clinical conclusions.** Reference ranges and normal/abnormal judgements are
   not synthesised here. ``abnormal`` is set only when the document itself carries
   an abnormality marker (``H``, ``L``, ``critical`` …).
4. **Uncertainty is reported, not resolved.** Weak transcription or an ambiguous
   match yields ``needs_review=True`` on the value instead of a confident number.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

from app.services.document_ocr import (
    LOW_CONFIDENCE_THRESHOLD,
    OcrDocument,
    OcrLine,
)

EXTRACTION_METHOD = "deterministic-line-regex"
EXTRACTION_VERSION = "1.0.0"

#: alias (lower-case) → canonical analyte label.
#: Recognition vocabulary only — deliberately carries no thresholds or ranges.
_ANALYTE_ALIASES: dict[str, str] = {
    # Haematology
    "wbc": "WBC",
    "white blood cell": "WBC",
    "white blood cells": "WBC",
    "rbc": "RBC",
    "red blood cell": "RBC",
    "red blood cells": "RBC",
    "hgb": "Hemoglobin",
    "hb": "Hemoglobin",
    "haemoglobin": "Hemoglobin",
    "hemoglobin": "Hemoglobin",
    "hct": "Hematocrit",
    "hematocrit": "Hematocrit",
    "haematocrit": "Hematocrit",
    "mcv": "MCV",
    "mch": "MCH",
    "mchc": "MCHC",
    "rdw": "RDW",
    "plt": "Platelet",
    "platelet": "Platelet",
    "platelets": "Platelet",
    "esr": "ESR",
    "crp": "CRP",
    "hs-crp": "CRP",
    # Chemistry
    "glucose": "Glucose",
    "fbs": "Fasting Blood Sugar",
    "fasting blood sugar": "Fasting Blood Sugar",
    "bs": "Blood Sugar",
    "hba1c": "HbA1c",
    "a1c": "HbA1c",
    "creatinine": "Creatinine",
    "cr": "Creatinine",
    "bun": "BUN",
    "urea": "Urea",
    "uric acid": "Uric Acid",
    "na": "Sodium",
    "sodium": "Sodium",
    "k": "Potassium",
    "potassium": "Potassium",
    "cl": "Chloride",
    "chloride": "Chloride",
    "ca": "Calcium",
    "calcium": "Calcium",
    "mg": "Magnesium",
    "magnesium": "Magnesium",
    "phosphorus": "Phosphorus",
    "phos": "Phosphorus",
    # Liver / protein
    "alt": "ALT",
    "sgpt": "ALT",
    "ast": "AST",
    "sgot": "AST",
    "alp": "ALP",
    "alkaline phosphatase": "ALP",
    "ggt": "GGT",
    "bilirubin": "Bilirubin",
    "total bilirubin": "Bilirubin (Total)",
    "direct bilirubin": "Bilirubin (Direct)",
    "albumin": "Albumin",
    "total protein": "Total Protein",
    # Thyroid
    "tsh": "TSH",
    "t3": "T3",
    "t4": "T4",
    "free t4": "Free T4",
    "ft4": "Free T4",
    # Lipids
    "cholesterol": "Cholesterol",
    "total cholesterol": "Cholesterol (Total)",
    "ldl": "LDL",
    "hdl": "HDL",
    "triglyceride": "Triglycerides",
    "triglycerides": "Triglycerides",
    "tg": "Triglycerides",
    # Coagulation / cardiac
    "inr": "INR",
    "pt": "PT",
    "ptt": "PTT",
    "aptt": "aPTT",
    "troponin": "Troponin",
    "d-dimer": "D-Dimer",
    "ck-mb": "CK-MB",
    "bnp": "BNP",
    # Iron studies / vitamins
    "ferritin": "Ferritin",
    "iron": "Iron",
    "tibc": "TIBC",
    "vitamin d": "Vitamin D",
    "25-oh vitamin d": "Vitamin D",
    "vitamin b12": "Vitamin B12",
    "b12": "Vitamin B12",
    "folate": "Folate",
}

#: Longest aliases first so "total cholesterol" wins over "cholesterol".
_ALIAS_PATTERN = "|".join(
    re.escape(alias)
    for alias in sorted(_ANALYTE_ALIASES, key=len, reverse=True)
)

#: Units are captured verbatim; this list only decides *where the unit ends*.
_UNIT_PATTERN = (
    r"(?:mg/dl|mg/dL|g/dl|g/dL|mmol/l|mmol/L|mcmol/L|µmol/L|umol/L|"
    r"meq/l|mEq/L|ng/ml|ng/mL|pg/ml|pg/mL|µIU/mL|uIU/mL|mIU/L|IU/L|U/L|"
    r"10\^3/µL|10\^3/uL|10\^6/µL|10\^6/uL|/µL|/uL|mm/hr|mm/h|fL|pg|%|sec|s)"
)

_VALUE_RE = re.compile(
    rf"\b(?P<key>{_ALIAS_PATTERN})\b"
    r"[\s:=.\-–—|‌]{0,6}"
    r"(?P<value>-?\d{1,3}(?:,\d{3})*(?:\.\d+)?|-?\d+(?:\.\d+)?)"
    rf"\s*(?P<unit>{_UNIT_PATTERN})?",
    re.IGNORECASE,
)

#: Abnormality markers the *document* itself supplies. Never inferred.
_ABNORMAL_MARKER_RE = re.compile(
    r"(?:\bH\b|\bL\b|\bHH\b|\bLL\b|\bhigh\b|\blow\b|\babnormal\b|"
    r"\belevated\b|\bcritical\b|\bpanic\b|\*)",
)

#: A value token this long is almost certainly a merged/garbled OCR artefact.
_MAX_VALUE_DIGITS = 9


@dataclass(frozen=True)
class ValueProvenance:
    """Where a single extracted value came from."""

    page: int
    #: (left, top, width, height) on the rendered page; None for PDF text layers.
    bbox: tuple[int, int, int, int] | None
    #: The exact transcribed substring the value was read from.
    source_text: str
    #: Full transcribed line, for reviewer context.
    line_text: str
    #: OCR confidence for the source token in [0.0, 1.0]; None when unreported.
    confidence: float | None
    method: str = EXTRACTION_METHOD
    method_version: str = EXTRACTION_VERSION


@dataclass(frozen=True)
class ExtractedValue:
    """One analyte reading with provenance."""

    name: str
    #: Verbatim numeric text as transcribed — never reformatted.
    value: str
    #: Verbatim unit as transcribed, or None when the document omitted it.
    unit: str | None
    provenance: ValueProvenance
    #: Document-declared abnormality only.
    abnormal: bool = False
    #: True when this reading must be confirmed by a human before clinical use.
    needs_review: bool = False
    review_reason: str | None = None

    def to_payload(self) -> dict:
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "abnormal": self.abnormal,
            "needs_review": self.needs_review,
            "review_reason": self.review_reason,
            "provenance": {
                "page": self.provenance.page,
                "bbox": list(self.provenance.bbox)
                if self.provenance.bbox is not None
                else None,
                "source_text": self.provenance.source_text,
                "line_text": self.provenance.line_text,
                "confidence": self.provenance.confidence,
                "method": self.provenance.method,
                "method_version": self.provenance.method_version,
            },
        }


@dataclass(frozen=True)
class ExtractionResult:
    """Structured extraction for one document."""

    values: tuple[ExtractedValue, ...] = field(default_factory=tuple)
    #: Whole-document review flag (e.g. transcription confidence too low).
    needs_review: bool = False
    review_reason: str | None = None

    @property
    def is_empty(self) -> bool:
        return not self.values

    def to_payload(self) -> dict:
        return {
            "schema": "clinical-extraction",
            "method": EXTRACTION_METHOD,
            "method_version": EXTRACTION_VERSION,
            "needs_review": self.needs_review,
            "review_reason": self.review_reason,
            "values": [value.to_payload() for value in self.values],
        }

    def summary_text(self) -> str:
        """Compact human-readable digest, used for legacy string surfaces.

        Values still needing review are marked so a reader can never mistake an
        uncertain transcription for a confirmed result.
        """
        parts: list[str] = []
        for value in self.values:
            rendered = f"{value.name}: {value.value}"
            if value.unit:
                rendered = f"{rendered} {value.unit}"
            if value.needs_review:
                rendered = f"{rendered} (needs review)"
            parts.append(rendered)
        return ", ".join(parts)


def _canonical_name(raw_key: str) -> str:
    return _ANALYTE_ALIASES.get(raw_key.strip().lower(), raw_key.strip())


def _word_bbox_for(line: OcrLine, token: str) -> tuple[int, int, int, int] | None:
    """Bounding box of the transcribed word carrying ``token``, else the line box."""
    normalized = token.replace(",", "")
    for word in line.words:
        candidate = word.text.replace(",", "")
        if normalized and normalized in candidate:
            if word.bbox is not None:
                return word.bbox
    return line.bbox


def _token_confidence(line: OcrLine, token: str) -> float | None:
    normalized = token.replace(",", "")
    for word in line.words:
        if normalized and normalized in word.text.replace(",", ""):
            if word.confidence is not None:
                return word.confidence
    return line.confidence


def _extract_from_line(line: OcrLine) -> list[ExtractedValue]:
    values: list[ExtractedValue] = []
    seen_spans: set[tuple[int, int]] = set()

    for match in _VALUE_RE.finditer(line.text):
        span = match.span()
        if span in seen_spans:
            continue
        seen_spans.add(span)

        raw_value = match.group("value")
        # Digit-count guard: a 12-digit "value" is a merged OCR artefact, not a lab
        # result. Flag for review rather than publishing a fabricated number.
        digits = re.sub(r"\D", "", raw_value)
        confidence = _token_confidence(line, raw_value)

        needs_review = False
        review_reason: str | None = None
        if len(digits) > _MAX_VALUE_DIGITS:
            needs_review = True
            review_reason = "implausible_value_length"
        elif confidence is not None and confidence < LOW_CONFIDENCE_THRESHOLD:
            needs_review = True
            review_reason = "low_ocr_confidence"

        unit = match.group("unit")
        values.append(
            ExtractedValue(
                name=_canonical_name(match.group("key")),
                value=raw_value,
                unit=unit.strip() if unit else None,
                abnormal=bool(_ABNORMAL_MARKER_RE.search(line.text[span[1] :])),
                needs_review=needs_review,
                review_reason=review_reason,
                provenance=ValueProvenance(
                    page=line.page,
                    bbox=_word_bbox_for(line, raw_value),
                    source_text=match.group(0).strip(),
                    line_text=line.text,
                    confidence=confidence,
                ),
            )
        )
    return values


def _dedupe(values: Iterable[ExtractedValue]) -> tuple[ExtractedValue, ...]:
    """Keep the first reading per (analyte, page).

    Lab reports repeat analyte names in headers/legends; the first occurrence next
    to a number is the reading. Later duplicates are dropped rather than merged so
    no synthetic "average" value is ever produced.
    """
    kept: list[ExtractedValue] = []
    seen: set[tuple[str, int]] = set()
    for value in values:
        key = (value.name.lower(), value.provenance.page)
        if key in seen:
            continue
        seen.add(key)
        kept.append(value)
    return tuple(kept)


def extract_clinical_values(document: OcrDocument) -> ExtractionResult:
    """Extract analyte readings with provenance from a transcribed document."""
    collected: list[ExtractedValue] = []
    for line in document.lines:
        collected.extend(_extract_from_line(line))

    values = _dedupe(collected)

    if document.needs_review:
        return ExtractionResult(
            values=values,
            needs_review=True,
            review_reason="low_document_ocr_confidence",
        )

    if any(value.needs_review for value in values):
        return ExtractionResult(
            values=values,
            needs_review=True,
            review_reason="one_or_more_values_need_review",
        )

    return ExtractionResult(values=values)
