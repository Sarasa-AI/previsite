"""Iranian mobile number normalization to E.164 (+98…)."""

from __future__ import annotations

import re

_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_E164_IR_MOBILE = re.compile(r"^\+989\d{9}$")


def to_ascii_digits(value: str) -> str:
    """Convert Persian / Arabic-Indic digits to ASCII."""
    return (value or "").translate(_PERSIAN_DIGITS)


def normalize_iranian_mobile(raw: str) -> str | None:
    """Normalize Iranian mobile to canonical E.164 ``+989xxxxxxxxx``.

    Accepts ``+98``, ``0098``, ``09xx``, ``9xx`` forms (with optional spaces
    or dashes). Returns None when the number is not a valid Iranian mobile.
    """
    if raw is None:
        return None
    text = to_ascii_digits(str(raw)).strip()
    if not text:
        return None

    # Strip common separators / zero-width characters used as obfuscation.
    text = re.sub(r"[\s\-_.\u200b\u200c\u200d\ufeff]+", "", text)

    if text.startswith("0098"):
        text = "+98" + text[4:]
    elif text.startswith("+98"):
        pass
    elif text.startswith("98") and len(text) >= 12 and text[2:].isdigit():
        # Country code without plus (0098 stripped already); need 98 + 10 national digits.
        text = "+" + text
    elif text.startswith("09"):
        text = "+98" + text[1:]
    elif text.startswith("9") and len(text) == 10 and text.isdigit():
        text = "+98" + text
    elif text.startswith("0") and len(text) == 11 and text.isdigit():
        if text.startswith("09"):
            text = "+98" + text[1:]
        else:
            return None
    else:
        return None

    if not _E164_IR_MOBILE.fullmatch(text):
        return None
    return text


def mask_phone_for_log(phone_e164: str) -> str:
    """Mask all but last 3 digits for logs (never log full phone)."""
    if not phone_e164 or len(phone_e164) < 3:
        return "***"
    return f"***{phone_e164[-3:]}"


def phone_last3(phone_e164: str) -> str:
    return (phone_e164 or "")[-3:]


def phone_email_local_part(phone_e164: str) -> str:
    """Digits-only local part for synthetic patient email."""
    return re.sub(r"\D", "", phone_e164 or "")
