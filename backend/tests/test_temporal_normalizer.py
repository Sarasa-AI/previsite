"""Tests for TemporalNormalizer (English + common Persian)."""

from __future__ import annotations

from datetime import datetime, timezone

from app.modules.timeline.domain.enums import TemporalKind, TemporalPrecision
from app.modules.timeline.infrastructure.temporal_normalizer import TemporalNormalizer

ANCHOR = datetime(2026, 7, 24, 12, 0, 0, tzinfo=timezone.utc)


def _norm(text: str):
    return TemporalNormalizer().normalize(text, anchor_at=ANCHOR)


def test_today() -> None:
    result = _norm("today")
    assert result.kind == TemporalKind.TODAY
    assert result.absolute_datetime == ANCHOR
    assert result.precision == TemporalPrecision.DAY
    assert result.uncertainty is False


def test_yesterday() -> None:
    result = _norm("yesterday")
    assert result.kind == TemporalKind.YESTERDAY
    assert result.absolute_datetime is not None
    assert (ANCHOR - result.absolute_datetime).days == 1


def test_absolute_iso_date() -> None:
    result = _norm("2024-03-15")
    assert result.kind == TemporalKind.ABSOLUTE
    assert result.absolute_datetime is not None
    assert result.absolute_datetime.year == 2024
    assert result.absolute_datetime.month == 3
    assert result.absolute_datetime.day == 15


def test_two_days_ago() -> None:
    result = _norm("2 days ago")
    assert result.kind == TemporalKind.RELATIVE_PAST
    assert result.relative_value == 2
    assert result.relative_unit == "days"
    assert result.absolute_datetime is not None
    assert (ANCHOR - result.absolute_datetime).days == 2


def test_last_week() -> None:
    result = _norm("last week")
    assert result.kind == TemporalKind.RELATIVE_PAST
    assert result.relative_unit == "weeks"
    assert result.relative_value == 1


def test_for_three_months() -> None:
    result = _norm("for 3 months")
    assert result.kind == TemporalKind.RELATIVE_DURATION
    assert result.relative_value == 3
    assert result.relative_unit == "months"


def test_for_three_days_word() -> None:
    result = _norm("for three days")
    assert result.kind == TemporalKind.RELATIVE_DURATION
    assert result.relative_value == 3
    assert result.relative_unit == "days"


def test_since_childhood() -> None:
    result = _norm("since childhood")
    assert result.kind == TemporalKind.RELATIVE_SINCE
    assert result.absolute_datetime is None
    assert result.uncertainty is True


def test_persian_five_years() -> None:
    result = _norm("۵ سال")
    assert result.kind == TemporalKind.RELATIVE_DURATION
    assert result.relative_value == 5
    assert result.relative_unit == "years"


def test_persian_three_days_ago() -> None:
    result = _norm("۳ روز پیش")
    assert result.kind == TemporalKind.RELATIVE_PAST
    assert result.relative_value == 3
    assert result.relative_unit == "days"


def test_persian_since_childhood() -> None:
    result = _norm("از کودکی")
    assert result.kind == TemporalKind.RELATIVE_SINCE


def test_unknown_empty() -> None:
    result = _norm("")
    assert result.kind == TemporalKind.UNKNOWN
    assert result.precision == TemporalPrecision.UNKNOWN
    assert result.uncertainty is True


def test_unknown_token() -> None:
    result = _norm("unknown")
    assert result.kind == TemporalKind.UNKNOWN


def test_diagnosed_year() -> None:
    result = _norm("diagnosed in 2018")
    assert result.kind == TemporalKind.ABSOLUTE
    assert result.absolute_datetime is not None
    assert result.absolute_datetime.year == 2018
    assert result.precision == TemporalPrecision.YEAR


def test_recurring_cue() -> None:
    result = _norm("every week")
    assert result.recurring is True


def test_raw_text_preserved() -> None:
    result = _norm("for 3 months")
    assert result.raw_text == "for 3 months"
