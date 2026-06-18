import logging
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum

from openai import AsyncOpenAI

from app.core.config import settings
from app.schemas.medical import MedicalSummary

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    """مدل‌های LLM پشتیبانی شده"""
    OPENROUTER = "openrouter"


class SOAPNoteGenerator:
    """
    سرویس تولید خودکار یادداشت‌های بالینی SOAP
    
    ویژگی‌ها:
    - پشتیبانی از OpenAI GPT-4 و Anthropic Claude و GapGPT
    - ترکیب داده‌های چندمنبعی (خلاصه پزشکی، چت، فایل‌ها)
    - تولید SOAP note استاندارد با ICD-10
    - مدیریت خطا و logging پیشرفته
    """

    def __init__(self):
        """راه‌اندازی کلاینت‌های LLM"""
        self.openrouter_client = None

        http_client = httpx.AsyncClient(proxies=settings.HTTP_PROXY, timeout=60.0)

        if settings.openrouter_api_key and settings.openrouter_api_key.strip():
            self.openrouter_client = AsyncOpenAI(
                base_url=settings.openrouter_base_url,
                api_key=settings.openrouter_api_key,
                http_client=http_client,
                default_headers={
                    "HTTP-Referer": settings.openrouter_http_referer,
                    "X-Title": settings.openrouter_app_title,
                },
            )
            logger.info("OpenRouter client initialized (Async)")

        if not self.openrouter_client:
            logger.warning("No LLM provider configured")

    def _get_system_prompt(self) -> str:
        """
        پرامپت سیستمی برای تولید SOAP note
        
        Returns:
            پرامپت ساختاریافته با دستورالعمل‌های دقیق
        """
        return """شما یک دستیار مستندسازی بالینی حرفه‌ای هستید که یادداشت‌های SOAP استاندارد تولید می‌کنید.

**ساختار SOAP**

**S - Subjective (ذهنی)**
- شکایت اصلی (Chief Complaint)
- تاریخچه بیماری فعلی (History of Present Illness)
- سابقه پزشکی گذشته (Past Medical History)
- داروهای فعلی (Current Medications)
- آلرژی‌ها (Allergies)
- سابقه خانوادگی/اجتماعی مرتبط (Family/Social History)

**O - Objective (عینی)**
- علائم حیاتی (Vital Signs)
- یافته‌های معاینه فیزیکی (Physical Exam)
- نتایج آزمایش (Lab Results)
- یافته‌های تصویربرداری (Imaging Findings)

**A - Assessment (ارزیابی)**
- تشخیص‌های افتراقی (Differential Diagnosis)
- تشخیص نهایی (Clinical Impression)
- کد ICD-10 (در صورت امکان)
- شدت و پیش‌آگهی (Severity & Prognosis)

**P - Plan (برنامه)**
- داروها (Medications) - نام، دوز، مدت
- آزمایش‌ها (Tests/Labs)
- تصویربرداری (Imaging)
- توصیه‌های سبک زندگی (Lifestyle Modifications)
- برنامه پیگیری (Follow-up Plan)
- ارجاع به متخصص (Referrals)

**قوانین:**
1. از اصطلاحات پزشکی استاندارد استفاده کنید
2. مختصر و دقیق باشید
3. اگر داده‌ای موجود نیست، بنویسید: "Not documented"
4. خروجی را به صورت Markdown تمیز فرمت کنید
5. از جداول برای داده‌های ساختاریافته استفاده کنید
6. کدهای ICD-10 را با فرمت `[ICD-10: X00.0]` بنویسید
7. اولویت‌بندی در Plan: فوری → کوتاه‌مدت → بلندمدت
"""

    def _build_context(
        self,
        summary: MedicalSummary,
        chat_history: Optional[List[Dict[str, str]]] = None,
        file_analyses: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        ساخت context جامع برای تولید SOAP
        
        Args:
            summary: خلاصه اطلاعات پزشکی استخراج شده
            chat_history: تاریخچه مکالمه با بیمار
            chat_history: تاریخچه مکالمه
            file_analyses: نتایج تحلیل فایل‌های پزشکی
        
        Returns:
            متن context ساختاریافته
        """

        sections: List[str] = []

        # ─────────── Metadata ───────────
        sections.append("=== VISIT METADATA ===")
        sections.append(f"Generated At: {datetime.utcnow().isoformat()}")
        sections.append(f"Patient ID: {getattr(summary, 'patient_id', 'Unknown')}")
        sections.append("")

        # ─────────── Structured Medical Summary ───────────
        sections.append("=== STRUCTURED MEDICAL SUMMARY ===")

        field_mapping = {
            "Chief Complaint": summary.chief_complaint,
            "Symptoms": ", ".join(summary.symptoms) if summary.symptoms else None,
            "Duration": summary.symptom_duration,
            "Severity": summary.symptom_severity,
            "Past Medical History": ", ".join(summary.past_medical_history) if summary.past_medical_history else None,
            "Current Medications": ", ".join(summary.current_medications) if summary.current_medications else None,
            "Allergies": ", ".join(summary.allergies) if summary.allergies else None,
            "Smoking Status": summary.smoking_status,
            "Alcohol Use": summary.alcohol_use,
            "Additional Notes": summary.additional_notes,
        }

        for label, value in field_mapping.items():
            if value:
                sections.append(f"{label}: {value}")

        if summary.review_of_systems:
            sections.append("Review of Systems:")
            for system, findings in summary.review_of_systems.items():
                sections.append(f"- {system}: {findings}")

        sections.append("")

        # ─────────── Chat History ───────────
        if chat_history:
            sections.append("=== CONSULTATION DIALOGUE (Last 20 Messages) ===")

            for msg in chat_history[-20:]:
                role = msg.get("role", "unknown").capitalize()
                content = msg.get("content", "")
                sections.append(f"{role}: {content}")

            sections.append("")

        # ─────────── File Analysis ───────────
        if file_analyses:
            sections.append("=== MEDICAL FILE ANALYSIS ===")

            for file_data in file_analyses:

                if file_data.get("lab_results"):
                    sections.append("Lab Results:")
                    for lab in file_data["lab_results"]:
                        sections.append(
                            f"- {lab.get('test_name')} | {lab.get('value')} {lab.get('unit')}"
                        )

                if file_data.get("diagnoses"):
                    sections.append("Diagnoses: " + ", ".join(file_data["diagnoses"]))

                if file_data.get("imaging_findings"):
                    sections.append("Imaging Findings: " + file_data["imaging_findings"])

                sections.append("")

        return "\n".join(sections)



    async def _generate_with_openrouter(self, context: str) -> str:
        """تولید SOAP با OpenRouter"""

        response = await self.openrouter_client.chat.completions.create(
            model=settings.openrouter_default_model,
            temperature=0.2,
            max_tokens=2500,
            messages=[
                {"role": "system", "content": self._get_system_prompt()},
                {"role": "user", "content": context},
            ],
        )

        return response.choices[0].message.content.strip()



    async def generate_soap_note(
        self,
        summary: MedicalSummary,
        chat_history: Optional[List[Dict[str, str]]] = None,
        file_analyses: Optional[List[Dict[str, Any]]] = None,
        preferred_provider: Optional[LLMProvider] = None,
    ) -> Dict[str, Any]:
        """
        اینترفیس اصلی تولید SOAP

        Returns:
            Dict شامل:
            - status
            - soap_note
            - provider
            - generated_at
            - confidence_score
        """

        try:
            context = self._build_context(summary, chat_history, file_analyses)

            # انتخاب provider
            provider = None
            note = None

            if self.openrouter_client:
                provider = LLMProvider.OPENROUTER
                note = await self._generate_with_openrouter(context)
            else:
                raise ValueError("No LLM provider configured")

            return {
                "status": "success",
                "provider": provider.value,
                "soap_note": note,
                "confidence_score": summary.confidence_score,
                "generated_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.exception("SOAP generation failed")

            return {
                "status": "error",
                "message": str(e),
                "generated_at": datetime.utcnow().isoformat(),
            }


# Singleton instance
soap_generator = SOAPNoteGenerator()
