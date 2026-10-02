"""Deterministic PHI scrubber for outbound LLM payloads (versioned rules).

Synthetic / known-identifier replacement only — no ML NER in this phase.
Residual risk: third-party names in free text are not detected.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping

from app.core.config import settings
from app.utils.national_id import validate_iranian_national_id
from app.utils.phone import to_ascii_digits

SCRUBBER_VERSION = "1"

_ZW_CLASS = r"[\s\u200b\u200c\u200d\ufeff\-_]*"

_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    re.IGNORECASE,
)
_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_MOBILE_RE = re.compile(r"(?:\+98|0098|98|0)?9\d{9}")
_LANDLINE_RE = re.compile(r"0[1-8]\d{9,10}")
_TEN_DIGIT_RE = re.compile(r"(?<!\d)\d{10}(?!\d)")
_GREGORIAN_RE = re.compile(
    r"\b(?:\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4})\b"
)
_JALALI_RE = re.compile(
    r"(?:1[34]\d{2}|۱۳[۰-۹]{2})[/\-.][۰-۹0-9]{1,2}[/\-.][۰-۹0-9]{1,2}"
)


@dataclass
class PatientKnownIds:
    name_parts: list[str] = field(default_factory=list)
    phone: str | None = None
    national_id: str | None = None
    email: str | None = None


@dataclass
class ScrubResult:
    text: str
    counts: dict[str, int] = field(default_factory=dict)
    placeholders: dict[str, str] = field(default_factory=dict)


class ScrubberError(Exception):
    """Raised when scrubbing cannot complete safely (fail closed)."""


def _bump(counts: dict[str, int], key: str, n: int = 1) -> None:
    counts[key] = counts.get(key, 0) + n


def _variants(value: str) -> list[str]:
    if not value:
        return []
    ascii_val = to_ascii_digits(value).strip()
    out = {value.strip(), ascii_val}
    digits = re.sub(r"\D", "", ascii_val)
    if digits:
        out.add(digits)
        out.add(" ".join(digits))
        out.add("-".join(digits))
    return [v for v in out if len(v) >= 2]


def scrub_text(
    text: str,
    *,
    known: PatientKnownIds | None = None,
    date_mode: str | None = None,
) -> ScrubResult:
    try:
        return _scrub_text_inner(
            text, known=known or PatientKnownIds(), date_mode=date_mode
        )
    except ScrubberError:
        raise
    except Exception as exc:
        raise ScrubberError(f"Scrubber failed: {exc}") from exc


def _scrub_text_inner(
    text: str,
    *,
    known: PatientKnownIds,
    date_mode: str | None,
) -> ScrubResult:
    if text is None:
        raise ScrubberError("Cannot scrub None")
    if not isinstance(text, str):
        text = str(text)

    mode = (date_mode or settings.llm_scrub_date_mode or "year").strip().lower()
    counts: dict[str, int] = {}
    placeholders: dict[str, str] = {}
    n = 0

    def _ph(category: str, original: str) -> str:
        nonlocal n
        n += 1
        token = f"[REDACTED_{category.upper()}_{n}]"
        placeholders[token] = original
        _bump(counts, category)
        return token

    working = to_ascii_digits(text)

    # Known identifiers (longest first).
    known_pairs: list[tuple[str, str]] = []
    for part in known.name_parts:
        for v in _variants(part):
            known_pairs.append(("name", v))
    if known.phone:
        for v in _variants(known.phone):
            known_pairs.append(("phone", v))
    if known.national_id:
        for v in _variants(known.national_id):
            known_pairs.append(("national_id", v))
    if known.email:
        for v in _variants(known.email):
            known_pairs.append(("email", v))
    known_pairs.sort(key=lambda x: len(x[1]), reverse=True)

    for category, value in known_pairs:
        working = re.compile(re.escape(value), re.IGNORECASE).sub(
            lambda m, cat=category: _ph(cat, m.group(0)), working
        )
        digits = re.sub(r"\D", "", to_ascii_digits(value))
        if len(digits) >= 8:
            loose = re.compile(_ZW_CLASS.join(re.escape(d) for d in digits))
            working = loose.sub(lambda m, cat=category: _ph(cat, m.group(0)), working)

    working = _EMAIL_RE.sub(lambda m: _ph("email", m.group(0)), working)
    working = _URL_RE.sub(lambda m: _ph("url", m.group(0)), working)

    def _sub_nid(m: re.Match) -> str:
        candidate = m.group(0)
        if validate_iranian_national_id(candidate):
            return _ph("national_id", candidate)
        return candidate

    working = _TEN_DIGIT_RE.sub(_sub_nid, working)
    working = _MOBILE_RE.sub(lambda m: _ph("phone", m.group(0)), working)
    working = _LANDLINE_RE.sub(lambda m: _ph("phone", m.group(0)), working)

    def _sub_date(m: re.Match) -> str:
        original = m.group(0)
        if mode == "remove":
            _bump(counts, "date")
            return ""
        digits = re.sub(r"\D", "", to_ascii_digits(original))
        year = digits[:4] if len(digits) >= 4 else "YEAR"
        _ph("date", original)  # record mapping
        return year

    working = _GREGORIAN_RE.sub(_sub_date, working)
    working = _JALALI_RE.sub(_sub_date, working)

    return ScrubResult(text=working, counts=counts, placeholders=placeholders)


def scrub_messages(
    messages: list[dict[str, Any]],
    *,
    known: PatientKnownIds | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int], dict[str, str]]:
    known = known or PatientKnownIds()
    total_counts: dict[str, int] = {}
    all_ph: dict[str, str] = {}
    out: list[dict[str, Any]] = []
    for msg in messages:
        content = msg.get("content")
        new_msg = dict(msg)
        if isinstance(content, str):
            result = scrub_text(content, known=known)
            new_msg["content"] = result.text
            for k, v in result.counts.items():
                _bump(total_counts, k, v)
            all_ph.update(result.placeholders)
        elif isinstance(content, list):
            scrubbed_parts = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    r = scrub_text(str(part.get("text", "")), known=known)
                    scrubbed_parts.append({**part, "text": r.text})
                    for k, v in r.counts.items():
                        _bump(total_counts, k, v)
                    all_ph.update(r.placeholders)
                else:
                    scrubbed_parts.append(part)
            new_msg["content"] = scrubbed_parts
        out.append(new_msg)
    return out, total_counts, all_ph


def rehydrate_text(text: str, placeholders: Mapping[str, str]) -> str:
    if not text or not placeholders:
        return text
    result = text
    for token in sorted(placeholders.keys(), key=len, reverse=True):
        result = result.replace(token, placeholders[token])
    return result


def omit_structured_identifiers(payload: Mapping[str, Any]) -> dict[str, Any]:
    forbidden = {
        "name",
        "full_name",
        "first_name",
        "last_name",
        "national_id",
        "phone",
        "email",
        "address",
        "date_of_birth",
        "dob",
        "birth_date",
    }
    return {k: v for k, v in payload.items() if k not in forbidden}


def messages_contain_image(messages: list[dict[str, Any]]) -> bool:
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") in (
                    "image_url",
                    "image",
                    "input_image",
                ):
                    return True
                if isinstance(part, dict) and "image_url" in part:
                    return True
        if isinstance(content, str) and content.startswith("data:image"):
            return True
    return False
