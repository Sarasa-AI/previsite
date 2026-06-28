import logging
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.schemas.medical import MedicalSummary, SoapNote
from app.services.rag_service import RagService, rag_service as default_rag_service

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

    def __init__(self, rag_service: RagService | None = None):
        """راه‌اندازی کلاینت‌های LLM"""
        self.rag_service = rag_service or default_rag_service
        self.openrouter_client = None

        http_client_kwargs = {"timeout": 60.0}
        if settings.HTTP_PROXY and settings.HTTP_PROXY.strip():
            http_client_kwargs["proxies"] = settings.HTTP_PROXY
        http_client = httpx.AsyncClient(**http_client_kwargs)

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

    def _extract_patient_hpi(self, summary: MedicalSummary) -> str:
        if summary.additional_notes and summary.additional_notes.strip():
            return summary.additional_notes.strip()

        parts: List[str] = []
        if summary.chief_complaint:
            parts.append(summary.chief_complaint.strip())
        if summary.symptoms:
            parts.append(", ".join(summary.symptoms))
        for field in (
            summary.symptom_duration,
            summary.symptom_severity,
            summary.symptom_onset,
            summary.symptom_character,
            summary.symptom_location,
            summary.symptom_radiation,
            summary.symptom_timing,
        ):
            if field:
                parts.append(field.strip())

        if parts:
            return ". ".join(parts)

        if summary.chief_complaint:
            return summary.chief_complaint.strip()

        return "general clinical presentation"

    def _format_medical_evidence(self, results: List[dict]) -> str:
        if not results:
            return ""

        lines = ["### Medical Evidence:"]
        for index, result in enumerate(results, start=1):
            source = result.get("source") or "Unknown source"
            content = result.get("content", "")
            lines.append(f"[{index}] {source}: {content}")

        return "\n".join(lines)

    def _build_citations(self, results: List[dict]) -> List[dict]:
        citations: List[dict] = []
        for index, result in enumerate(results, start=1):
            citations.append(
                {
                    "index": index,
                    "source": result.get("source") or "Unknown source",
                    "content": result.get("content", ""),
                    "confidence": result.get("confidence"),
                }
            )
        return citations

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

**Medical Evidence (الزامی در صورت ارائه)**
Use the following retrieved clinical evidence to support your assessment. You MUST cite sources using [1], [2], etc., where numbers correspond to the evidence list provided below.
- Apply retrieved evidence primarily in Assessment and Plan sections.
- Only cite evidence that appears in the Medical Evidence block of the user message.
- If no Medical Evidence block is provided, do not include citation markers.

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
        db: AsyncSession,
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
            - citations
            - provider
            - generated_at
            - confidence_score
        """

        try:
            patient_hpi = self._extract_patient_hpi(summary)
            knowledge_results: List[dict] = []

            try:
                knowledge_results = await self.rag_service.search_similar_knowledge(
                    db, query=patient_hpi
                )
            except Exception:
                logger.warning(
                    "RAG retrieval failed for SOAP generation; continuing without evidence",
                    exc_info=True,
                )

            citations = self._build_citations(knowledge_results)
            context = self._build_context(summary, chat_history, file_analyses)
            evidence_block = self._format_medical_evidence(knowledge_results)
            if evidence_block:
                context = f"{context}\n\n{evidence_block}"

            provider = None
            note = None

            if self.openrouter_client:
                provider = LLMProvider.OPENROUTER
                note = await self._generate_with_openrouter(context)
            else:
                raise ValueError("No LLM provider configured")

            soap = SoapNote(content=note, citations=citations)

            return {
                "status": "success",
                "provider": provider.value,
                "soap_note": soap.content,
                "citations": soap.citations,
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
