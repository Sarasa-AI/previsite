import logging
import httpx
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Dict, Any, List, Optional, Set
from datetime import datetime
from enum import Enum

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.schemas.medical import MedicalSummary, SoapNote, VerificationStatus
from app.services.rag_service import RagService, rag_service as default_rag_service

logger = logging.getLogger(__name__)

CITATION_SIMILARITY_THRESHOLD = 0.35
_CITATION_MARKER_RE = re.compile(r"\[(\d+)\]")


@dataclass
class CitationVerificationResult:
    content: str
    citations: List[dict]
    verification_status: VerificationStatus


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

    @staticmethod
    def _normalize_for_similarity(text: str) -> str:
        normalized = text.lower()
        normalized = re.sub(r"[^\w\s]", " ", normalized)
        return re.sub(r"\s+", " ", normalized).strip()

    @staticmethod
    def _content_similarity(sentence: str, chunk: str) -> float:
        normalized_sentence = SOAPNoteGenerator._normalize_for_similarity(sentence)
        normalized_chunk = SOAPNoteGenerator._normalize_for_similarity(chunk)
        if not normalized_sentence or not normalized_chunk:
            return 0.0

        ratio = SequenceMatcher(None, normalized_sentence, normalized_chunk).ratio()
        sentence_tokens = set(normalized_sentence.split())
        chunk_tokens = set(normalized_chunk.split())
        overlap = (
            len(sentence_tokens & chunk_tokens) / len(sentence_tokens)
            if sentence_tokens
            else 0.0
        )
        return max(ratio, overlap)

    @staticmethod
    def _extract_citation_indices(text: str) -> Set[int]:
        return {int(match) for match in _CITATION_MARKER_RE.findall(text)}

    @staticmethod
    def _extract_citing_context(text: str, index: int) -> str:
        marker = f"[{index}]"
        segments = re.split(r"(?<=[.!?\n])", text)
        for segment in segments:
            if marker in segment:
                return segment.replace(marker, "").strip()
        return text.replace(marker, "").strip()

    @staticmethod
    def _strip_citation_markers(text: str, indices: Set[int]) -> str:
        cleaned = text
        for index in sorted(indices, reverse=True):
            cleaned = cleaned.replace(f"[{index}]", "")
        return re.sub(r"  +", " ", cleaned)

    def _compute_aggregate_verification_status(
        self,
        annotated_citations: List[dict],
        used_indices: Set[int],
        has_citations: bool,
    ) -> VerificationStatus:
        if not used_indices and not has_citations:
            return "verified"

        if used_indices and not has_citations:
            return "unverified"

        used_statuses = [
            citation["verification_status"]
            for citation in annotated_citations
            if citation.get("index") in used_indices
        ]

        if not used_indices:
            return "verified"

        if all(status == "verified" for status in used_statuses):
            return "verified"
        if any(status == "verified" for status in used_statuses):
            return "partially_verified"
        return "unverified"

    async def verify_citations(
        self, soap_note_text: str, citations: List[dict]
    ) -> List[dict]:
        """
        Verify citation markers in the SOAP note against retrieved evidence.

        Returns annotated citations with per-entry verification_status.
        """
        result = await self._apply_citation_verification(soap_note_text, citations)
        return result.citations

    async def _apply_citation_verification(
        self, soap_note_text: str, citations: List[dict]
    ) -> CitationVerificationResult:
        citation_map = {citation["index"]: citation for citation in citations}
        used_indices = self._extract_citation_indices(soap_note_text)
        annotated_citations: List[dict] = []
        indices_to_strip: Set[int] = set()
        similarity_scores: Dict[int, float] = {}

        for citation in citations:
            index = citation["index"]
            annotated = {**citation}

            if index not in used_indices:
                annotated["verification_status"] = "unused"
                annotated_citations.append(annotated)
                continue

            citing_context = self._extract_citing_context(soap_note_text, index)
            chunk_content = citation.get("content", "")
            similarity = self._content_similarity(citing_context, chunk_content)
            similarity_scores[index] = similarity

            if similarity >= CITATION_SIMILARITY_THRESHOLD:
                annotated["verification_status"] = "verified"
            else:
                annotated["verification_status"] = "unverified"
                indices_to_strip.add(index)
                logger.warning(
                    "Citation [%s] failed similarity check (score=%.2f)",
                    index,
                    similarity,
                )

            annotated_citations.append(annotated)

        for index in used_indices:
            if index in citation_map:
                continue

            annotated_citations.append(
                {
                    "index": index,
                    "source": None,
                    "content": "",
                    "confidence": None,
                    "verification_status": "unverified",
                }
            )
            indices_to_strip.add(index)
            logger.warning("Citation [%s] references index not in retrieved evidence", index)

        verification_status = self._compute_aggregate_verification_status(
            annotated_citations,
            used_indices,
            has_citations=bool(citations),
        )

        cleaned_content = soap_note_text
        if indices_to_strip:
            cleaned_content = self._strip_citation_markers(soap_note_text, indices_to_strip)
        elif used_indices and not citations:
            cleaned_content = self._strip_citation_markers(soap_note_text, used_indices)

        return CitationVerificationResult(
            content=cleaned_content,
            citations=annotated_citations,
            verification_status=verification_status,
        )

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
        file_analyses: Optional[List[Dict[str, Any]]] = None,
        pmh_context: str | None = None,
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

        if pmh_context:
            sections.append("### Patient Past Medical History (From Questionnaire):")
            sections.append(pmh_context)
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
        pmh_context: str | None = None,
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
            context = self._build_context(
                summary, chat_history, file_analyses, pmh_context=pmh_context
            )
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

            verification = await self._apply_citation_verification(note, citations)
            soap = SoapNote(
                content=verification.content,
                citations=verification.citations,
                verification_status=verification.verification_status,
            )

            return {
                "status": "success",
                "provider": provider.value,
                "soap_note": soap.content,
                "citations": soap.citations,
                "verification_status": soap.verification_status,
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
