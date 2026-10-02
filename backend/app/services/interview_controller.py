import json
from typing import Optional, List, Dict

from app.services.interview_flow import InterviewStage
from app.schemas.medical import MedicalSummary


class InterviewController:

    _UNKNOWN_VALUES = {"نامشخص", "unknown", "n/a", "na", ""}

    def _is_missing(self, value) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            return value.strip().lower() in self._UNKNOWN_VALUES
        if isinstance(value, (list, dict)):
            return len(value) == 0
        return False

    def _format_recent_messages(
        self,
        chat_history: Optional[List[Dict[str, str]]],
        limit: int = 3,
    ) -> str:
        if not chat_history:
            return "هنوز پیامی رد و بدل نشده است."

        recent = chat_history[-limit:]
        lines = []
        for msg in recent:
            role = "بیمار" if msg.get("role") == "user" else "دستیار"
            content = msg.get("content", "").strip()
            if content:
                lines.append(f"- {role}: {content}")
        return "\n".join(lines) if lines else "هنوز پیامی رد و بدل نشده است."

    def _format_summary(self, summary: Optional[MedicalSummary]) -> str:
        if not summary:
            return "هنوز اطلاعات پزشکی استخراج نشده است."
        summary_dict = summary.model_dump(exclude_none=True, exclude={"extracted_at"})
        return json.dumps(summary_dict, ensure_ascii=False, indent=2)

    def is_diagnostic_sufficient(self, summary: MedicalSummary) -> bool:
        """
        Check if HPI is sufficient (has onset, severity, and character)
        """
        has_onset = not self._is_missing(summary.symptom_onset)
        has_severity = not self._is_missing(summary.symptom_severity)
        has_character = not self._is_missing(summary.symptom_character)
        return has_onset and has_severity and has_character

    def _hpi_is_incomplete(self, summary: MedicalSummary) -> bool:
        """
        بررسی ناقص بودن HPI.
        Now uses is_diagnostic_sufficient instead of just is_hpi_complete flag.
        """
        return not self.is_diagnostic_sufficient(summary)

    def _social_history_incomplete(self, summary: MedicalSummary) -> bool:
        return (
            self._is_missing(summary.smoking_status)
            and self._is_missing(summary.alcohol_use)
        )

    def detect_stage(
        self,
        summary: Optional[MedicalSummary],
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> InterviewStage:
        """
        تعیین مرحله مصاحبه بر اساس خلاصه پزشکی استخراج‌شده و زمینه گفتگو.
        """
        if not summary or self._is_missing(summary.chief_complaint):
            return InterviewStage.CHIEF_COMPLAINT

        if self._hpi_is_incomplete(summary):
            return InterviewStage.OPQRST

        if self._is_missing(summary.review_of_systems) and self._is_missing(summary.symptoms):
            return InterviewStage.ASSOCIATED_SYMPTOMS

        if self._is_missing(summary.past_medical_history):
            return InterviewStage.PAST_MEDICAL_HISTORY

        if self._is_missing(summary.current_medications):
            return InterviewStage.MEDICATIONS

        if self._is_missing(summary.allergies):
            return InterviewStage.ALLERGIES

        if self._social_history_incomplete(summary):
            return InterviewStage.SOCIAL_HISTORY

        return InterviewStage.COMPLETION

    def get_stage_instruction(
        self,
        stage: InterviewStage,
        summary: Optional[MedicalSummary] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        recent_messages = self._format_recent_messages(chat_history)
        summary_text = self._format_summary(summary)

        stage_focus = {
            InterviewStage.CHIEF_COMPLAINT: "شکایت اصلی، زمان شروع، و نگرانی فوری بیمار",
            InterviewStage.OPQRST: "جزئیات شرح حال فعلی (شروع، شدت، عوامل تشدید/بهبود، پیشرفت، علائم همراه)",
            InterviewStage.ASSOCIATED_SYMPTOMS: "علائم همراه و بررسی سیستم‌های مرتبط",
            InterviewStage.PAST_MEDICAL_HISTORY: "سابقه بیماری، جراحی‌ها و بستری‌های قبلی",
            InterviewStage.MEDICATIONS: "داروهای فعلی و دوز مصرف",
            InterviewStage.ALLERGIES: "آلرژی‌های دارویی یا غذایی",
            InterviewStage.FAMILY_HISTORY: "سابقه بیماری در خانواده",
            InterviewStage.SOCIAL_HISTORY: "سیگار، الکل، شغل و عوامل محیطی",
            InterviewStage.COMPLETION: "جمع‌بندی و پایان گفتگو در صورت کافی بودن اطلاعات",
        }

        focus = stage_focus.get(stage, "مهم‌ترین خلأ اطلاعاتی باقی‌مانده")

        if stage == InterviewStage.COMPLETION:
            return f"""
خلاصه پزشکی استخراج‌شده:
{summary_text}

۳ پیام آخر گفتگو:
{recent_messages}

اگر اطلاعات برای ارزیابی اولیه کافی است، گفتگو را با جمله پایانی مشخص‌شده در دستورالعمل سیستمی تمام کن.
در غیر این صورت، بزرگ‌ترین خلأ باقی‌مانده را شناسایی کن و یک سوال طبیعی بپرس.
"""

        return f"""
۳ پیام آخر گفتگو:
{recent_messages}

خلاصه پزشکی استخراج‌شده:
{summary_text}

تمرکز پیشنهادی این نوبت: {focus}

دستورالعمل:
- ۳ پیام آخر و خلاصه پزشکی بالا را مرور کن.
- بزرگ‌ترین خلأ اطلاعاتی را شناسایی کن (نه لزوماً به ترتیب ثابت).
- یک سوال پیگیری طبیعی و گفت‌وگومحور بساز که همدلانه باشد و استدلال پزشکی نشان دهد.
- از تکرار سوالاتی که بیمار قبلاً پاسخ داده خودداری کن.
- فقط یک سوال بپرس.
"""


interview_controller = InterviewController()
