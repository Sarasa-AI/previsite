import re

HPI_FIELD_LABELS_FA: dict[str, str] = {
    "course": "روند علامت",
    "onset": "شروع",
    "severity": "شدت",
    "associated": "علائم همراه",
    "fever": "تب",
    "redflag_severe": "علائم هشداردهنده",
    "reason_for_testing": "علت آزمایش",
    "symptoms_present": "وجود علائم",
    "thirst": "تشنگی",
    "weight_loss": "کاهش وزن",
    "urgent_symptoms": "علائم فوری",
    "followup_reason": "هدف ویزیت",
    "current_status": "وضعیت فعلی",
    "new_symptoms": "علائم جدید",
    "urination": "ادرار",
    "hypoglycemia_symptoms": "علائم افت قند",
    "location": "محل",
    "duration": "مدت",
    "character": "کیفیت",
    "radiation": "انتشار",
    "timing": "زمان‌بندی",
}

GENDER_FA: dict[str, str] = {
    "male": "مرد",
    "female": "زن",
}

RAW_KV_PATTERN = re.compile(r"\b[a-z_]+:\s*\S")
ENGLISH_TOKEN_PATTERN = re.compile(r"\b(male|female|true|false|none)\b", re.IGNORECASE)


def sex_label_fa(sex: str | None) -> str:
    if not sex:
        return "نامشخص"
    normalized = sex.strip().lower()
    return GENDER_FA.get(normalized, sex)


def validate_narrative(text: str) -> bool:
    if not text or not text.strip():
        return False
    if RAW_KV_PATTERN.search(text):
        return False
    if ENGLISH_TOKEN_PATTERN.search(text):
        return False
    return True


def build_hpi_narrative_fallback(
    *,
    age: int,
    sex: str,
    chief_complaint: str,
    hpi_answers: dict[str, str],
) -> str:
    """Build clean Persian prose when LLM narration fails."""
    sex_fa = sex_label_fa(sex)
    parts = [
        f"بیمار {age} ساله {sex_fa} با شکایت {chief_complaint} مراجعه کرده است."
    ]

    for key, value in hpi_answers.items():
        if not value or not str(value).strip():
            continue
        label = HPI_FIELD_LABELS_FA.get(key, key.replace("_", " "))
        parts.append(f"{label}: {value.strip()}")

    return " ".join(parts)
