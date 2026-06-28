import logging
import asyncio
import json

from pydantic import BaseModel, Field

from app.schemas.intake import ClinicalSummary, DemographicsInput, HPIQuestionsResponse
from app.services.narrative_utils import (
    build_hpi_narrative_fallback,
    sex_label_fa,
    validate_narrative,
)
from app.services.openrouter_service import OpenRouterServiceError, openrouter_service

logger = logging.getLogger(__name__)

LAYER2_SYSTEM_PROMPT = """You are a medical intake assistant for a Persian-speaking clinic and telemedicine platform.
Your task is to generate the most relevant Present Illness questions based on the patient's: Age, Sex, Chief Complaint.
The questions will be shown to the patient by the application one at a time.
Important rules:
- The patient is Persian-speaking. All questions must be written in simple, natural Persian understandable to the general public.
- First internally classify the visit into one of the following categories: Acute symptom, Chronic disease follow-up, Laboratory/test result review, Preventive checkup. Do NOT reveal this classification to the patient.
- Generate only questions related to the Present Illness (current reason for visit).
- Do NOT ask about: Past medical history, Medication history, Drug use, Allergies, Family history, Laboratory values, Previous surgeries.
- Do NOT diagnose.
- Do NOT suggest treatments.
- Do NOT mention possible diseases.
- Prioritize patient safety by including relevant red-flag questions when appropriate.
- Ask only high-yield questions that help a physician understand the current problem.
- Avoid duplicate or overlapping questions.
- Limit the number of questions to the minimum needed to understand the current problem.
- Return valid JSON only.

Question Writing Guidelines:
- Keep questions short.
- Ask one concept per question.
- Use conversational Persian.
- Prefer symptom-focused questions.
- For chronic disease follow-up visits, focus on current control, symptoms, concerns, and reason for follow-up.
- For laboratory review visits, focus on the context and symptoms related to the abnormal result.
- For preventive checkups, focus on goals, concerns, and any current symptoms.
- For acute symptoms, focus on onset, duration, severity, progression, associated symptoms, and red flags.

JSON Output Schema:
{ "question_strategy": "brief explanation for developers", "questions": [ { "id": "short_identifier", "question": "Persian question", "priority": 1, "red_flag_related": false } ] }"""

EXTRACTION_SYSTEM_PROMPT = """You are a clinical documentation assistant for physicians.
Extract structured clinical data from patient intake answers.
Rules:
- Use only information provided in the input.
- Never invent symptoms, findings, diagnoses, or negative findings.
- Never infer diagnoses.
- Never suggest treatments.
- Output valid JSON only.

JSON Output Schema:
{ "chief_complaint": "Brief physician-facing chief complaint.", "pertinent_positives": ["Important symptoms or findings reported"], "pertinent_negatives": ["Important symptoms specifically denied"], "red_flags": ["Potentially concerning findings explicitly reported"] }"""

NARRATION_SYSTEM_PROMPT = """You are a clinical documentation assistant for physicians.
Write a concise Persian clinical narrative (hpi_summary) for the History of Present Illness section.
Rules:
- Write fluent professional Persian medical prose, NOT key-value pairs.
- Never use English words like male, female, true, false, none.
- Use only information provided in the input.
- Never invent symptoms or findings.
- Do not use JSON field names or colon-separated labels in the narrative.
- Output valid JSON only with a single field.

JSON Output Schema:
{ "hpi_summary": "Concise narrative summary of the present illness in fluent Persian." }"""

INTERVIEW_CHAT_BASE_PROMPT = """شما یک دستیار پزشکی هوشمند و همدل هستید که در حال انجام مصاحبه با بیمار به زبان فارسی هستید.

هدف شما: جمع‌آوری تاریخچه پزشکی کامل بیمار به صورت گفت‌وگوی طبیعی و محترمانه — نه پرسشنامه ثابت.

زمینه بالینی استخراج‌شده تاکنون:
{clinical_context}

گفتگوی اخیر (پاسخ‌های قبلی بیمار):
{recent_conversation}

دستورالعمل‌های کلی:
- فقط و فقط «یک» سوال در هر نوبت بپرسید.
- سوالات را کوتاه، روان و محترمانه نگه دارید.
- در صورت ابراز درد یا نگرانی، با بیمار همدلی کنید.
- پاسخ‌های شما نباید بیش از ۲ یا ۳ جمله باشد.

تولید سوال پویا:
- سوالات را تکرار نکنید. اگر بیمار قبلاً اطلاعاتی داده، دوباره درباره همان موضوع نپرسید.
- ۳ پیام آخر و خلاصه بالینی را مرور کنید، بزرگ‌ترین خلأ اطلاعاتی را شناسایی کنید، و یک سوال پیگیری طبیعی بسازید.
- بر اساس لحن بیمار و شکایت اصلی فعلی، سوالی بپرسید که همدلی و استدلال پزشکی نشان دهد.
- از الگوی ثابت پرسشنامه‌ای خودداری کنید؛ گفتگو باید ادامه طبیعی مکالمه قبلی باشد.

- هرگاه تمام اطلاعات لازم را جمع‌آوری کردید، دقیقاً با این جمله گفتگو را تمام کنید: "ممنون از همکاری شما. اطلاعات کافی جمع‌آوری شد. subject object plan"
"""


def _format_recent_conversation(chat_history: list[dict], limit: int = 5) -> str:
    if not chat_history:
        return "هنوز گفتگویی ثبت نشده است."

    recent = chat_history[-limit:]
    lines = []
    for msg in recent:
        role = "بیمار" if msg.get("role") == "user" else "دستیار"
        content = msg.get("content", "").strip()
        if content:
            lines.append(f"- {role}: {content}")
    return "\n".join(lines) if lines else "هنوز گفتگویی ثبت نشده است."


def build_interview_system_prompt(
    clinical_context: str = "",
    chat_history: list[dict] | None = None,
    stage_instruction: str = "",
) -> str:
    prompt = INTERVIEW_CHAT_BASE_PROMPT.format(
        clinical_context=clinical_context or "هنوز داده‌ای استخراج نشده است.",
        recent_conversation=_format_recent_conversation(chat_history or []),
    )
    if stage_instruction.strip():
        prompt += f"\n\nدستورالعمل این نوبت:\n{stage_instruction.strip()}"
    return prompt


class ClinicalExtraction(BaseModel):
    chief_complaint: str
    pertinent_positives: list[str] = Field(default_factory=list)
    pertinent_negatives: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)


class HpiNarration(BaseModel):
    hpi_summary: str


def _build_layer2_user_prompt(demographics: DemographicsInput) -> str:
    sex_fa = sex_label_fa(demographics.sex)
    return f"""Patient Information
Age: {demographics.age}
Sex: {sex_fa}
Chief Complaint: {demographics.chief_complaint}
Generate the Present Illness questions."""


def _build_extraction_user_prompt(
    demographics: DemographicsInput,
    hpi_answers: dict[str, str],
) -> str:
    sex_fa = sex_label_fa(demographics.sex)
    return f"""Patient Information
Age: {demographics.age}
Sex: {sex_fa}
Chief Complaint: {demographics.chief_complaint}
Present Illness Answers: {json.dumps(hpi_answers, ensure_ascii=False)}
Extract structured clinical data."""


def _build_narration_user_prompt(
    demographics: DemographicsInput,
    hpi_answers: dict[str, str],
    extracted: ClinicalExtraction,
) -> str:
    sex_fa = sex_label_fa(demographics.sex)
    return f"""Patient Information
Age: {demographics.age}
Sex: {sex_fa}
Chief Complaint: {demographics.chief_complaint}
Present Illness Answers: {json.dumps(hpi_answers, ensure_ascii=False)}
Extracted Positives: {json.dumps(extracted.pertinent_positives, ensure_ascii=False)}
Extracted Negatives: {json.dumps(extracted.pertinent_negatives, ensure_ascii=False)}
Extracted Red Flags: {json.dumps(extracted.red_flags, ensure_ascii=False)}
Write a fluent Persian hpi_summary narrative."""


def _fallback_questions(demographics: DemographicsInput) -> HPIQuestionsResponse:
    """Deterministic fallback when LLM is unavailable."""
    complaint = demographics.chief_complaint.lower()

    if any(kw in complaint for kw in ("دیابت", "فشار خون", "قلب", "دوره‌ای", "پیگیری")):
        return HPIQuestionsResponse(
            question_strategy="Chronic disease follow-up workflow focused on current status, symptom burden, and reason for follow-up.",
            questions=[
                {"id": "followup_reason", "question": "هدف اصلی شما از این ویزیت دوره‌ای چیست؟", "priority": 1, "red_flag_related": False},
                {"id": "current_status", "question": "در حال حاضر وضعیت بیماری خود را نسبت به قبل چگونه ارزیابی می‌کنید؟", "priority": 2, "red_flag_related": False},
                {"id": "new_symptoms", "question": "از آخرین ویزیت تاکنون علامت یا مشکل جدیدی پیدا کرده‌اید؟", "priority": 3, "red_flag_related": False},
                {"id": "thirst", "question": "آیا اخیراً تشنگی بیش از حد معمول داشته‌اید؟", "priority": 4, "red_flag_related": False},
                {"id": "urination", "question": "آیا دفعات ادرار شما بیشتر از قبل شده است؟", "priority": 5, "red_flag_related": False},
                {"id": "hypoglycemia_symptoms", "question": "آیا دچار لرزش، تعریق یا ضعف ناگهانی شده‌اید؟", "priority": 6, "red_flag_related": True},
            ],
        )

    if any(kw in complaint for kw in ("آزمایش", "چکاپ", "نتیجه", "خون")):
        return HPIQuestionsResponse(
            question_strategy="Laboratory result review workflow focused on context, symptoms, and urgency assessment.",
            questions=[
                {"id": "reason_for_testing", "question": "این آزمایش به چه دلیلی انجام شده بود؟", "priority": 1, "red_flag_related": False},
                {"id": "symptoms_present", "question": "آیا در حال حاضر علامت یا مشکلی دارید که باعث نگرانی شما شده باشد؟", "priority": 2, "red_flag_related": False},
                {"id": "thirst", "question": "آیا اخیراً تشنگی بیش از حد معمول داشته‌اید؟", "priority": 3, "red_flag_related": False},
                {"id": "weight_loss", "question": "آیا اخیراً بدون رژیم یا ورزش کاهش وزن داشته‌اید؟", "priority": 4, "red_flag_related": False},
                {"id": "urgent_symptoms", "question": "آیا تهوع شدید، استفراغ، گیجی یا ضعف شدید دارید؟", "priority": 5, "red_flag_related": True},
            ],
        )

    return HPIQuestionsResponse(
        question_strategy="Acute symptom workflow focused on location, timing, severity, associated symptoms, and red flags.",
        questions=[
            {"id": "onset", "question": "این مشکل از چه زمانی شروع شده است؟", "priority": 1, "red_flag_related": False},
            {"id": "course", "question": "وضعیت از زمان شروع بهتر شده، بدتر شده یا تغییری نکرده است؟", "priority": 2, "red_flag_related": False},
            {"id": "severity", "question": "شدت علامت را از ۰ تا ۱۰ چقدر ارزیابی می‌کنید؟", "priority": 3, "red_flag_related": False},
            {"id": "associated", "question": "آیا علامت دیگری همراه با آن دارید؟", "priority": 4, "red_flag_related": False},
            {"id": "fever", "question": "آیا تب یا لرز داشته‌اید؟", "priority": 5, "red_flag_related": False},
            {"id": "redflag_severe", "question": "آیا علامت آنقدر شدید است که انجام فعالیت‌های روزمره را مختل کرده باشد؟", "priority": 6, "red_flag_related": True},
        ],
    )


def _fallback_extraction(
    demographics: DemographicsInput,
    hpi_answers: dict[str, str],
) -> ClinicalExtraction:
    return ClinicalExtraction(
        chief_complaint=demographics.chief_complaint,
        pertinent_positives=list(hpi_answers.values()),
        pertinent_negatives=[],
        red_flags=[],
    )


def _fallback_clinical_summary(
    demographics: DemographicsInput,
    hpi_answers: dict[str, str],
    extracted: ClinicalExtraction | None = None,
) -> ClinicalSummary:
    structured = extracted or _fallback_extraction(demographics, hpi_answers)
    hpi_text = build_hpi_narrative_fallback(
        age=demographics.age,
        sex=demographics.sex,
        chief_complaint=structured.chief_complaint,
        hpi_answers=hpi_answers,
    )

    return ClinicalSummary(
        chief_complaint=structured.chief_complaint,
        hpi_summary=hpi_text,
        pertinent_positives=structured.pertinent_positives,
        pertinent_negatives=structured.pertinent_negatives,
        red_flags=structured.red_flags,
    )


class IntakeLLMService:
    async def generate_hpi_questions(self, demographics: DemographicsInput) -> HPIQuestionsResponse:
        user_prompt = _build_layer2_user_prompt(demographics)

        try:
            parsed = await asyncio.wait_for(
                openrouter_service.generate_json(
                    system_prompt=LAYER2_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    temperature=0.0,
                ),
                timeout=15.0,
            )
            result = HPIQuestionsResponse.model_validate(parsed)
            result.questions.sort(key=lambda q: q.priority)
            return result
        except (OpenRouterServiceError, ValueError, TimeoutError) as exc:
            if isinstance(exc, TimeoutError):
                logger.warning("Layer 2 LLM fallback triggered: LLM response exceeded 15s SLA")
            else:
                logger.warning("Layer 2 LLM fallback triggered: %s", exc)
            return _fallback_questions(demographics)

    async def _extract_clinical_data(
        self,
        demographics: DemographicsInput,
        hpi_answers: dict[str, str],
    ) -> ClinicalExtraction:
        user_prompt = _build_extraction_user_prompt(demographics, hpi_answers)
        try:
            parsed = await asyncio.wait_for(
                openrouter_service.generate_json(
                    system_prompt=EXTRACTION_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    temperature=0.0,
                ),
                timeout=15.0,
            )
            return ClinicalExtraction.model_validate(parsed)
        except (OpenRouterServiceError, ValueError, TimeoutError) as exc:
            logger.warning("Clinical extraction fallback triggered: %s", exc)
            return _fallback_extraction(demographics, hpi_answers)

    async def _generate_hpi_narration(
        self,
        demographics: DemographicsInput,
        hpi_answers: dict[str, str],
        extracted: ClinicalExtraction,
    ) -> str:
        user_prompt = _build_narration_user_prompt(demographics, hpi_answers, extracted)
        max_attempts = 2

        for attempt in range(max_attempts):
            try:
                parsed = await asyncio.wait_for(
                    openrouter_service.generate_json(
                        system_prompt=NARRATION_SYSTEM_PROMPT,
                        user_prompt=user_prompt,
                        temperature=0.3,
                    ),
                    timeout=15.0,
                )
                narration = HpiNarration.model_validate(parsed)
                if validate_narrative(narration.hpi_summary):
                    return narration.hpi_summary
                logger.warning(
                    "HPI narration failed validation (attempt %s/%s)",
                    attempt + 1,
                    max_attempts,
                )
            except (OpenRouterServiceError, ValueError, TimeoutError) as exc:
                logger.warning(
                    "HPI narration LLM error (attempt %s/%s): %s",
                    attempt + 1,
                    max_attempts,
                    exc,
                )

        return build_hpi_narrative_fallback(
            age=demographics.age,
            sex=demographics.sex,
            chief_complaint=extracted.chief_complaint,
            hpi_answers=hpi_answers,
        )

    async def generate_clinical_summary(
        self,
        demographics: DemographicsInput,
        hpi_answers: dict[str, str],
    ) -> ClinicalSummary:
        extracted = await self._extract_clinical_data(demographics, hpi_answers)

        try:
            hpi_summary = await self._generate_hpi_narration(demographics, hpi_answers, extracted)
            return ClinicalSummary(
                chief_complaint=extracted.chief_complaint,
                hpi_summary=hpi_summary,
                pertinent_positives=extracted.pertinent_positives,
                pertinent_negatives=extracted.pertinent_negatives,
                red_flags=extracted.red_flags,
            )
        except Exception as exc:
            logger.warning("Clinical summary assembly fallback triggered: %s", exc)
            return _fallback_clinical_summary(demographics, hpi_answers, extracted)


intake_llm_service = IntakeLLMService()
