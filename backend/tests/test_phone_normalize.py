"""Phone normalization unit tests (synthetic numbers only)."""

from __future__ import annotations

import pytest

from app.utils.phone import normalize_iranian_mobile, to_ascii_digits


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("09121234567", "+989121234567"),
        ("+989121234567", "+989121234567"),
        ("00989121234567", "+989121234567"),
        ("9121234567", "+989121234567"),
        ("۰۹۱۲۱۲۳۴۵۶۷", "+989121234567"),
        ("٠٩١٢١٢٣٤٥٦٧", "+989121234567"),
        ("0912 123 4567", "+989121234567"),
        ("0912-123-4567", "+989121234567"),
        ("+98\u200c9121234567", "+989121234567"),
    ],
)
def test_normalize_valid(raw: str, expected: str) -> None:
    assert normalize_iranian_mobile(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "123",
        "08121234567",  # landline-style, not mobile
        "+98912123456",  # too short
        "+9891212345678",  # too long
        "abcdefghijk",
        None,
    ],
)
def test_normalize_invalid(raw) -> None:
    assert normalize_iranian_mobile(raw) is None  # type: ignore[arg-type]


def test_to_ascii_digits() -> None:
    assert to_ascii_digits("۰۱۲۳۴۵۶۷۸۹") == "0123456789"
    assert to_ascii_digits("٠١٢٣٤٥٦٧٨٩") == "0123456789"
