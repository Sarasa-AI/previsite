"""Deterministic temporal expression normalizer (English + common Persian)."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Literal

from dateutil import parser as date_parser

from app.modules.timeline.domain.enums import TemporalKind, TemporalPrecision
from app.modules.timeline.domain.models import TemporalExpression

RelativeUnit = Literal["days", "weeks", "months", "years"]

_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

_UNKNOWN_TOKENS = frozenset(
    {
        "",
        "unknown",
        "n/a",
        "na",
        "نامشخص",
        "نامعلوم",
        "مشخص نیست",
    }
)

_UNIT_MAP: dict[str, RelativeUnit] = {
    "day": "days",
    "days": "days",
    "روز": "days",
    "week": "weeks",
    "weeks": "weeks",
    "هفته": "weeks",
    "month": "months",
    "months": "months",
    "ماه": "months",
    "year": "years",
    "years": "years",
    "سال": "years",
}

_WORD_NUMBERS: dict[str, int] = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "a": 1,
    "an": 1,
    "few": 3,
    "یک": 1,
    "دو": 2,
    "سه": 3,
    "چهار": 4,
    "پنج": 5,
    "شش": 6,
    "هفت": 7,
    "هشت": 8,
    "نه": 9,
    "ده": 10,
}

_RECURRING_RE = re.compile(
    r"\b(every|each|recurring|weekly|daily|monthly|سالانه|ماهانه|هفته‌ای|هر\s+روز|هر\s+هفته)\b",
    re.IGNORECASE,
)

_RELATIVE_PAST_RE = re.compile(
    r"(?P<num>\d+|one|two|three|four|five|six|seven|eight|nine|ten|a|an|few|"
    r"یک|دو|سه|چهار|پنج|شش|هفت|هشت|نه|ده)"
    r"\s+"
    r"(?P<unit>days?|weeks?|months?|years?|روز|هفته|ماه|سال)"
    r"\s*(?:ago|پیش)",
    re.IGNORECASE,
)

_DURATION_FOR_RE = re.compile(
    r"(?:for|برای)\s+"
    r"(?P<num>\d+|one|two|three|four|five|six|seven|eight|nine|ten|a|an|few|"
    r"یک|دو|سه|چهار|پنج|شش|هفت|هشت|نه|ده)"
    r"\s+"
    r"(?P<unit>days?|weeks?|months?|years?|روز|هفته|ماه|سال)",
    re.IGNORECASE,
)

_BARE_DURATION_RE = re.compile(
    r"^(?:(?:for|برای)\s+)?"
    r"(?P<num>\d+|one|two|three|four|five|six|seven|eight|nine|ten|a|an|few|"
    r"یک|دو|سه|چهار|پنج|شش|هفت|هشت|نه|ده)"
    r"\s+"
    r"(?P<unit>days?|weeks?|months?|years?|روز|هفته|ماه|سال)"
    r"(?:\s+(?:now|ago|پیش))?$",
    re.IGNORECASE,
)

_DIAGNOSED_YEAR_RE = re.compile(
    r"(?:diagnosed|diagnosis|since|از)\s*(?:in\s*)?(?P<year>19\d{2}|20\d{2})",
    re.IGNORECASE,
)

_YEAR_ONLY_RE = re.compile(r"^(?P<year>19\d{2}|20\d{2})$")

_SINCE_CHILDHOOD_RE = re.compile(
    r"(since\s+childhood|از\s*کودکی|از\s*بچگی)",
    re.IGNORECASE,
)

_LAST_PERIOD_RE = re.compile(
    r"\blast\s+(?P<unit>week|month|year)\b",
    re.IGNORECASE,
)

_STARTED_LAST_RE = re.compile(
    r"(?:started|began|started\s+on)?\s*last\s+(?P<unit>week|month|year)",
    re.IGNORECASE,
)


def _normalize_text(raw: str) -> str:
    text = raw.translate(_PERSIAN_DIGITS).strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _parse_number(token: str) -> int | None:
    token = token.lower().strip()
    if token.isdigit():
        return int(token)
    return _WORD_NUMBERS.get(token)


def _unit_precision(unit: RelativeUnit) -> TemporalPrecision:
    if unit == "days":
        return TemporalPrecision.DAY
    if unit == "weeks":
        return TemporalPrecision.DAY
    if unit == "months":
        return TemporalPrecision.MONTH
    return TemporalPrecision.YEAR


def _shift_anchor(anchor: datetime, value: int, unit: RelativeUnit) -> datetime:
    if unit == "days":
        return anchor - timedelta(days=value)
    if unit == "weeks":
        return anchor - timedelta(weeks=value)
    if unit == "months":
        # Approximate calendar months without inventing exact days.
        return anchor - timedelta(days=30 * value)
    return anchor - timedelta(days=365 * value)


def _unknown(raw_text: str, *, recurring: bool = False) -> TemporalExpression:
    return TemporalExpression(
        kind=TemporalKind.UNKNOWN,
        raw_text=raw_text,
        precision=TemporalPrecision.UNKNOWN,
        uncertainty=True,
        recurring=recurring,
    )


class TemporalNormalizer:
    """Normalize free-text temporal expressions into structured TemporalExpression."""

    def normalize(
        self,
        text: str | None,
        *,
        anchor_at: datetime | None = None,
    ) -> TemporalExpression:
        anchor = anchor_at or datetime.now(timezone.utc)
        if anchor.tzinfo is None:
            anchor = anchor.replace(tzinfo=timezone.utc)

        raw = (text or "").strip()
        normalized = _normalize_text(raw)
        recurring = bool(_RECURRING_RE.search(normalized))

        if normalized.lower() in _UNKNOWN_TOKENS:
            return _unknown(raw or normalized, recurring=recurring)

        lower = normalized.lower()

        if lower in {"today", "امروز"}:
            return TemporalExpression(
                kind=TemporalKind.TODAY,
                raw_text=raw,
                absolute_datetime=anchor,
                precision=TemporalPrecision.DAY,
                uncertainty=False,
                recurring=recurring,
            )

        if lower in {"yesterday", "دیروز"}:
            return TemporalExpression(
                kind=TemporalKind.YESTERDAY,
                raw_text=raw,
                absolute_datetime=anchor - timedelta(days=1),
                precision=TemporalPrecision.DAY,
                uncertainty=False,
                recurring=recurring,
            )

        childhood = _SINCE_CHILDHOOD_RE.search(normalized)
        if childhood:
            return TemporalExpression(
                kind=TemporalKind.RELATIVE_SINCE,
                raw_text=raw,
                precision=TemporalPrecision.APPROXIMATE,
                uncertainty=True,
                recurring=recurring,
            )

        last_match = _LAST_PERIOD_RE.search(normalized) or _STARTED_LAST_RE.search(normalized)
        if last_match:
            unit_token = last_match.group("unit").lower()
            unit = _UNIT_MAP[unit_token]
            value = 1
            abs_dt = _shift_anchor(anchor, value, unit)
            return TemporalExpression(
                kind=TemporalKind.RELATIVE_PAST,
                raw_text=raw,
                absolute_datetime=abs_dt,
                relative_value=value,
                relative_unit=unit,
                precision=_unit_precision(unit),
                uncertainty=True,
                recurring=recurring,
            )

        past = _RELATIVE_PAST_RE.search(normalized)
        if past:
            value = _parse_number(past.group("num"))
            unit = _UNIT_MAP.get(past.group("unit").lower())
            if value is not None and unit is not None:
                return TemporalExpression(
                    kind=TemporalKind.RELATIVE_PAST,
                    raw_text=raw,
                    absolute_datetime=_shift_anchor(anchor, value, unit),
                    relative_value=value,
                    relative_unit=unit,
                    precision=_unit_precision(unit),
                    uncertainty=True,
                    recurring=recurring,
                )

        duration = _DURATION_FOR_RE.search(normalized) or _BARE_DURATION_RE.match(normalized)
        if duration:
            value = _parse_number(duration.group("num"))
            unit_key = duration.group("unit").lower()
            # Normalize plural English units for map lookup
            unit = _UNIT_MAP.get(unit_key) or _UNIT_MAP.get(unit_key.rstrip("s"))
            if value is not None and unit is not None:
                # "ago" bare-duration still relative past
                if re.search(r"\b(ago|پیش)\b", normalized, re.IGNORECASE):
                    return TemporalExpression(
                        kind=TemporalKind.RELATIVE_PAST,
                        raw_text=raw,
                        absolute_datetime=_shift_anchor(anchor, value, unit),
                        relative_value=value,
                        relative_unit=unit,
                        precision=_unit_precision(unit),
                        uncertainty=True,
                        recurring=recurring,
                    )
                return TemporalExpression(
                    kind=TemporalKind.RELATIVE_DURATION,
                    raw_text=raw,
                    absolute_datetime=_shift_anchor(anchor, value, unit),
                    relative_value=value,
                    relative_unit=unit,
                    precision=_unit_precision(unit),
                    uncertainty=True,
                    recurring=recurring,
                )

        diagnosed = _DIAGNOSED_YEAR_RE.search(normalized)
        if diagnosed:
            year = int(diagnosed.group("year"))
            abs_dt = datetime(year, 1, 1, tzinfo=timezone.utc)
            return TemporalExpression(
                kind=TemporalKind.ABSOLUTE,
                raw_text=raw,
                absolute_datetime=abs_dt,
                precision=TemporalPrecision.YEAR,
                uncertainty=True,
                recurring=recurring,
            )

        year_only = _YEAR_ONLY_RE.match(normalized)
        if year_only:
            year = int(year_only.group("year"))
            return TemporalExpression(
                kind=TemporalKind.ABSOLUTE,
                raw_text=raw,
                absolute_datetime=datetime(year, 1, 1, tzinfo=timezone.utc),
                precision=TemporalPrecision.YEAR,
                uncertainty=True,
                recurring=recurring,
            )

        # Approximate cues
        if re.search(r"\b(approx|approximately|about|around|حدود|تقریبا)\b", lower):
            # Try to still extract a duration/past inside approximate phrasing
            inner = re.sub(
                r"\b(approx|approximately|about|around|حدود|تقریبا)\b",
                "",
                normalized,
                flags=re.IGNORECASE,
            ).strip()
            if inner and inner != normalized:
                nested = self.normalize(inner, anchor_at=anchor)
                if nested.kind != TemporalKind.UNKNOWN:
                    return TemporalExpression(
                        kind=TemporalKind.APPROXIMATE,
                        raw_text=raw,
                        absolute_datetime=nested.absolute_datetime,
                        relative_value=nested.relative_value,
                        relative_unit=nested.relative_unit,
                        precision=TemporalPrecision.APPROXIMATE,
                        uncertainty=True,
                        recurring=recurring or nested.recurring,
                    )
            return TemporalExpression(
                kind=TemporalKind.APPROXIMATE,
                raw_text=raw,
                precision=TemporalPrecision.APPROXIMATE,
                uncertainty=True,
                recurring=recurring,
            )

        # Absolute date parsing via dateutil (dayfirst=False for ISO-friendly forms)
        try:
            parsed = date_parser.parse(normalized, fuzzy=True, default=anchor)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            # Reject if parse ignored all digits and returned default-like noise
            if any(ch.isdigit() for ch in normalized) or re.search(
                r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b",
                lower,
            ):
                precision = TemporalPrecision.DAY
                if re.fullmatch(r"\d{4}-\d{2}", normalized):
                    precision = TemporalPrecision.MONTH
                elif re.fullmatch(r"\d{4}", normalized):
                    precision = TemporalPrecision.YEAR
                return TemporalExpression(
                    kind=TemporalKind.ABSOLUTE,
                    raw_text=raw,
                    absolute_datetime=parsed,
                    precision=precision,
                    uncertainty=False,
                    recurring=recurring,
                )
        except (ValueError, OverflowError, TypeError):
            pass

        return _unknown(raw, recurring=recurring)


temporal_normalizer = TemporalNormalizer()
