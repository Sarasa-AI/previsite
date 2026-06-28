import json
from typing import Dict, List
from app.services.llm_service import llm_service


class MedicalSummaryBuilder:
    def _fallback_summary(self, messages: List[dict]) -> Dict:
        user_messages = [
            m["content"].strip()
            for m in messages
            if m.get("role") == "user" and isinstance(m.get("content"), str) and m["content"].strip()
        ]
        chief_complaint = user_messages[0] if user_messages else "نامشخص"
        history = "\n".join(user_messages[-3:]) if user_messages else "نامشخص"

        return {
            "chief_complaint": chief_complaint,
            "history_present_illness": history,
            "past_medical_history": "نامشخص",
            "medications": "نامشخص",
            "allergies": "نامشخص",
            "assessment": "اطلاعات اولیه بیمار ثبت شد و نیاز به بررسی پزشک دارد.",
            "is_hpi_complete": False
        }

    async def build_summary(self, messages: List[dict]) -> Dict:

        conversation = "\n".join([
            f"{m['role']}: {m['content']}" for m in messages
        ])

        prompt = f"""
از مکالمه زیر اطلاعات پزشکی بیمار را استخراج کن و خلاصه استاندارد بساز.

مکالمه:
{conversation}

خروجی فقط JSON باشد:

{{
"chief_complaint": "",
"history_present_illness": "",
"past_medical_history": "",
"medications": "",
"allergies": "",
"assessment": "",
"is_hpi_complete": false
}}

قوانین:
- به فارسی بنویس
- اگر اطلاعات ناقص است بنویس "نامشخص"
- فیلد is_hpi_complete را زمانی true کن که شرح حال فعلی (HPI) از نظر بالینی برای تشخیص افتراقی کافی باشد (شامل جزئیات کافی از شروع، کیفیت، علائم همراه و رد فرضیات مهم).
"""

        try:
            response = await llm_service.chat([
                {"role": "user", "content": prompt}
            ])
        except Exception:
            return self._fallback_summary(messages)

        try:
            return json.loads(response)
        except Exception:
            return self._fallback_summary(messages)


summary_builder = MedicalSummaryBuilder()
