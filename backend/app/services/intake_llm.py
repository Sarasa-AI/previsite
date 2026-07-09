import logging
import json
from dataclasses import dataclass

from pydantic import BaseModel, Field

from app.core.config import settings
from app.schemas.intake import ClinicalSummary, DemographicsInput, HPIQuestionsResponse
from app.services.llm_cascade import llm_cascade
from app.services.narrative_utils import (
    build_hpi_narrative_fallback,
    sex_label_fa,
    validate_narrative,
)

logger = logging.getLogger(__name__)

INTAKE_LLM_TIMEOUT = settings.intake_llm_timeout_seconds
INTAKE_MAX_TOKENS = 1200

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


@dataclass
class Layer2GenerationResult:
    questions: HPIQuestionsResponse
    llm_fallback_used: bool = False
    llm_error_message: str | None = None


@dataclass
class ClinicalSummaryResult:
    summary: ClinicalSummary
    llm_fallback_used: bool = False
    llm_error_message: str | None = None


def _classify_llm_error(exc: Exception) -> str:
    if isinstance(exc, TimeoutError):
        return f"Timeout: LLM response exceeded {INTAKE_LLM_TIMEOUT:g}s SLA"
    message = str(exc).strip() or type(exc).__name__
    lowered = message.lower()
    if "authentication" in lowered or "401" in lowered:
        return "Authentication error"
    if "connection" in lowered:
        return "Connection error"
    return message


def _log_layer2_fallback(
    *,
    session_id: int | None,
    chief_complaint: str,
    exc: Exception,
) -> str:
    error_message = _classify_llm_error(exc)
    logger.warning("Layer 2 LLM fallback triggered: %s", error_message)
    logger.error(
        "Intake Layer 2 fallback active | session_id=%s chief_complaint=%r error_type=%s detail=%s",
        session_id,
        chief_complaint,
        type(exc).__name__,
        error_message,
    )
    return error_message


def _log_layer3_fallback(
    *,
    session_id: int | None,
    chief_complaint: str,
    stage: str,
    exc: Exception,
) -> str:
    error_message = _classify_llm_error(exc)
    logger.warning("Layer 3 %s fallback triggered: %s", stage, error_message)
    logger.error(
        "Intake Layer 3 fallback active | session_id=%s stage=%s chief_complaint=%r error_type=%s detail=%s",
        session_id,
        stage,
        chief_complaint,
        type(exc).__name__,
        error_message,
    )
    return error_message


def _complaint_matches(complaint: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in complaint for keyword in keywords)


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
    """Deterministic diagnostic fallback when LLM is unavailable."""
    complaint = demographics.chief_complaint.strip().lower()

    if _complaint_matches(complaint, ("دیابت", "فشار خون", "قلب", "دوره‌ای", "پیگیری")):
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

    if _complaint_matches(complaint, ("آزمایش", "چکاپ", "نتیجه", "خون")):
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

    if _complaint_matches(complaint, ("قفسه سینه", "سینه", "تنگی نفس", "درد قلبی", "فشار سینه")):
        return HPIQuestionsResponse(
            question_strategy="Chest pain / dyspnea diagnostic workflow focused on cardiac and pulmonary red flags.",
            questions=[
                {"id": "chest_location", "question": "درد یا فشار دقیقاً کجای قفسه سینه احساس می‌شود؟", "priority": 1, "red_flag_related": False},
                {"id": "radiation", "question": "آیا درد به بازو، فک، گردن یا پشت منتشر می‌شود؟", "priority": 2, "red_flag_related": True},
                {"id": "exertion", "question": "آیا با فعالیت یا استرس بدتر می‌شود و با استراحت بهتر می‌شود؟", "priority": 3, "red_flag_related": True},
                {"id": "associated", "question": "آیا تعریق، تهوع، استفراغ یا تپش قلب همراه آن دارید؟", "priority": 4, "red_flag_related": True},
                {"id": "breathing", "question": "آیا همراه با تنگی نفس یا احساس خفگی است؟", "priority": 5, "red_flag_related": True},
                {"id": "severity", "question": "شدت درد یا فشار را از ۰ تا ۱۰ چقدر ارزیابی می‌کنید؟", "priority": 6, "red_flag_related": False},
            ],
        )

    if _complaint_matches(complaint, ("دل", "شکم", "دل‌درد", "درد شکم", "دل درد")):
        return HPIQuestionsResponse(
            question_strategy="Abdominal pain diagnostic workflow focused on location, character, and associated GI symptoms.",
            questions=[
                {"id": "abd_location", "question": "درد دقیقاً کجای شکم است؟ (بالا، پایین، راست، چپ)", "priority": 1, "red_flag_related": False},
                {"id": "abd_character", "question": "نوع درد چگونه است؟ (سوزش، گرفتگی، تیرکش، مداوم)", "priority": 2, "red_flag_related": False},
                {"id": "abd_onset", "question": "از چه زمانی شروع شده و تدریجی بوده یا ناگهانی؟", "priority": 3, "red_flag_related": False},
                {"id": "nausea_vomiting", "question": "آیا تهوع، استفراغ یا بی‌اشتهایی دارید؟", "priority": 4, "red_flag_related": False},
                {"id": "bowel", "question": "آیا تغییر در مدفوع، یبوست، اسهال یا خون در مدفوع داشته‌اید؟", "priority": 5, "red_flag_related": True},
                {"id": "abd_redflag", "question": "آیا تب، استفراغ خونی یا درد آنقدر شدید است که نتوانید راحت حرکت کنید؟", "priority": 6, "red_flag_related": True},
            ],
        )

    if _complaint_matches(complaint, ("سردرد", "سر درد", "میگرن")):
        return HPIQuestionsResponse(
            question_strategy="Headache diagnostic workflow focused on onset pattern, severity, and neurological red flags.",
            questions=[
                {"id": "headache_onset", "question": "سردرد ناگهانی و شدید بوده یا تدریجی شروع شده است؟", "priority": 1, "red_flag_related": True},
                {"id": "worst_ever", "question": "آیا شدیدترین سردردی است که تا به حال داشته‌اید؟", "priority": 2, "red_flag_related": True},
                {"id": "headache_location", "question": "درد در کدام قسمت سر است و یک طرفه است یا هر دو طرف؟", "priority": 3, "red_flag_related": False},
                {"id": "neuro_symptoms", "question": "آیا تاری دید، دوبینی، گیجی، ضعف اندام یا اختلال تکلم دارید؟", "priority": 4, "red_flag_related": True},
                {"id": "meningeal", "question": "آیا تب، گردن سفت یا حساس به نور دارید؟", "priority": 5, "red_flag_related": True},
                {"id": "headache_severity", "question": "شدت سردرد را از ۰ تا ۱۰ چقدر ارزیابی می‌کنید؟", "priority": 6, "red_flag_related": False},
            ],
        )

    if _complaint_matches(complaint, ("کاهش وزن", "لاغری", "کم شدن وزن", "افزایش وزن", "چاقی")):
        return HPIQuestionsResponse(
            question_strategy="Weight change diagnostic workflow focused on amount, timeline, appetite, and red flags.",
            questions=[
                {"id": "weight_amount", "question": "تقریباً چند کیلوگرم وزن کم یا زیاد کرده‌اید و در چه مدت؟", "priority": 1, "red_flag_related": False},
                {"id": "intentional", "question": "آیا عمداً رژیم، ورزش یا تغییر سبک زندگی داشته‌اید؟", "priority": 2, "red_flag_related": False},
                {"id": "appetite", "question": "اشتهای شما در این مدت چگونه بوده است؟", "priority": 3, "red_flag_related": False},
                {"id": "night_sweats", "question": "آیا تعریق شبانه یا تب خفیف داشته‌اید؟", "priority": 4, "red_flag_related": True},
                {"id": "gi_symptoms", "question": "آیا تهوع، استفراغ، درد شکم یا تغییر در مدفوع دارید؟", "priority": 5, "red_flag_related": True},
                {"id": "fatigue_bleeding", "question": "آیا خستگی شدید، خونریزی غیرطبیعی یا زردی چشم دارید؟", "priority": 6, "red_flag_related": True},
            ],
        )

    if _complaint_matches(complaint, ("سرفه", "تب", "لرز", "سرماخورد", "گلو")):
        return HPIQuestionsResponse(
            question_strategy="Respiratory / infectious symptom workflow focused on duration, severity, and red flags.",
            questions=[
                {"id": "onset_duration", "question": "علامت از چه زمانی شروع شده و چند روز است ادامه دارد؟", "priority": 1, "red_flag_related": False},
                {"id": "fever_pattern", "question": "آیا تب دارید؟ بالاترین دما چقدر بوده است؟", "priority": 2, "red_flag_related": False},
                {"id": "cough_character", "question": "سرفه خشک است یا همراه با خلط؟ اگر خلط دارید رنگ آن چیست؟", "priority": 3, "red_flag_related": True},
                {"id": "breathing", "question": "آیا تنگی نفس یا درد قفسه سینه با نفس کشیدن دارید؟", "priority": 4, "red_flag_related": True},
                {"id": "associated", "question": "آیا گلودرد، آبریزش بینی، بدن‌درد یا از دست دادن بویایی دارید؟", "priority": 5, "red_flag_related": False},
                {"id": "redflag_severe", "question": "آیا تنفس سخت شده، لب‌ها کبود شده یا خیلی ضعیف و گیج شده‌اید؟", "priority": 6, "red_flag_related": True},
            ],
        )

    return HPIQuestionsResponse(
        question_strategy="Acute symptom workflow focused on location, timing, progression, modifiers, associated symptoms, and red flags.",
        questions=[
            {"id": "location", "question": "محل دقیق علامت کجاست؟", "priority": 1, "red_flag_related": False},
            {"id": "onset", "question": "این مشکل از چه زمانی شروع شده است؟", "priority": 2, "red_flag_related": False},
            {"id": "course", "question": "وضعیت از زمان شروع بهتر شده، بدتر شده یا تغییری نکرده است؟", "priority": 3, "red_flag_related": False},
            {"id": "aggravating", "question": "چه چیزی علامت را بدتر می‌کند؟", "priority": 4, "red_flag_related": False},
            {"id": "associated", "question": "آیا علامت دیگری همراه با آن دارید؟", "priority": 5, "red_flag_related": False},
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
    async def generate_hpi_questions(
        self,
        demographics: DemographicsInput,
        *,
        session_id: int | None = None,
    ) -> Layer2GenerationResult:
        user_prompt = _build_layer2_user_prompt(demographics)

        cascade_result = await llm_cascade.generate_json_with_cascade(
            system_prompt=LAYER2_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            tier3_factory=lambda: _fallback_questions(demographics).model_dump(),
            temperature=0.0,
            max_tokens=INTAKE_MAX_TOKENS,
        )

        if cascade_result.llm_fallback_used:
            _log_layer2_fallback(
                session_id=session_id,
                chief_complaint=demographics.chief_complaint,
                exc=Exception(cascade_result.error_message or "LLM fallback used"),
            )

        result = HPIQuestionsResponse.model_validate(cascade_result.data)
        result.questions.sort(key=lambda q: q.priority)
        return Layer2GenerationResult(
            questions=result,
            llm_fallback_used=cascade_result.llm_fallback_used,
            llm_error_message=cascade_result.error_message,
        )

    async def _extract_clinical_data(
        self,
        demographics: DemographicsInput,
        hpi_answers: dict[str, str],
        *,
        session_id: int | None = None,
    ) -> tuple[ClinicalExtraction, bool, str | None]:
        user_prompt = _build_extraction_user_prompt(demographics, hpi_answers)

        cascade_result = await llm_cascade.generate_json_with_cascade(
            system_prompt=EXTRACTION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            tier3_factory=lambda: _fallback_extraction(
                demographics, hpi_answers
            ).model_dump(),
            temperature=0.0,
            max_tokens=INTAKE_MAX_TOKENS,
        )

        if cascade_result.llm_fallback_used:
            _log_layer3_fallback(
                session_id=session_id,
                chief_complaint=demographics.chief_complaint,
                stage="clinical extraction",
                exc=Exception(cascade_result.error_message or "LLM fallback used"),
            )

        return (
            ClinicalExtraction.model_validate(cascade_result.data),
            cascade_result.llm_fallback_used,
            cascade_result.error_message,
        )

    async def _generate_hpi_narration(
        self,
        demographics: DemographicsInput,
        hpi_answers: dict[str, str],
        extracted: ClinicalExtraction,
        *,
        session_id: int | None = None,
    ) -> tuple[str, bool, str | None]:
        user_prompt = _build_narration_user_prompt(demographics, hpi_answers, extracted)
        max_attempts = 2
        last_error: str | None = None

        for attempt in range(max_attempts):
            cascade_result = await llm_cascade.generate_json_with_cascade(
                system_prompt=NARRATION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                tier3_factory=lambda: {
                    "hpi_summary": build_hpi_narrative_fallback(
                        age=demographics.age,
                        sex=demographics.sex,
                        chief_complaint=extracted.chief_complaint,
                        hpi_answers=hpi_answers,
                    )
                },
                temperature=0.3,
                max_tokens=INTAKE_MAX_TOKENS,
            )

            if cascade_result.tier_used == 3:
                if cascade_result.llm_fallback_used:
                    last_error = cascade_result.error_message
                    _log_layer3_fallback(
                        session_id=session_id,
                        chief_complaint=demographics.chief_complaint,
                        stage=f"HPI narration attempt {attempt + 1}/{max_attempts}",
                        exc=Exception(last_error or "LLM fallback used"),
                    )
                narration = HpiNarration.model_validate(cascade_result.data)
                return narration.hpi_summary, True, last_error

            narration = HpiNarration.model_validate(cascade_result.data)
            if validate_narrative(narration.hpi_summary):
                return (
                    narration.hpi_summary,
                    cascade_result.llm_fallback_used,
                    cascade_result.error_message,
                )

            logger.warning(
                "HPI narration failed validation (attempt %s/%s)",
                attempt + 1,
                max_attempts,
            )
            if cascade_result.llm_fallback_used:
                last_error = cascade_result.error_message

        return (
            build_hpi_narrative_fallback(
                age=demographics.age,
                sex=demographics.sex,
                chief_complaint=extracted.chief_complaint,
                hpi_answers=hpi_answers,
            ),
            True,
            last_error,
        )

    async def generate_clinical_summary(
        self,
        demographics: DemographicsInput,
        hpi_answers: dict[str, str],
        *,
        session_id: int | None = None,
    ) -> ClinicalSummaryResult:
        extracted, extraction_fallback, extraction_error = await self._extract_clinical_data(
            demographics,
            hpi_answers,
            session_id=session_id,
        )

        try:
            hpi_summary, narration_fallback, narration_error = await self._generate_hpi_narration(
                demographics,
                hpi_answers,
                extracted,
                session_id=session_id,
            )
            fallback_used = extraction_fallback or narration_fallback
            error_message = extraction_error or narration_error
            return ClinicalSummaryResult(
                summary=ClinicalSummary(
                    chief_complaint=extracted.chief_complaint,
                    hpi_summary=hpi_summary,
                    pertinent_positives=extracted.pertinent_positives,
                    pertinent_negatives=extracted.pertinent_negatives,
                    red_flags=extracted.red_flags,
                ),
                llm_fallback_used=fallback_used,
                llm_error_message=error_message if fallback_used else None,
            )
        except Exception as exc:
            error_message = _log_layer3_fallback(
                session_id=session_id,
                chief_complaint=demographics.chief_complaint,
                stage="clinical summary assembly",
                exc=exc,
            )
            return ClinicalSummaryResult(
                summary=_fallback_clinical_summary(demographics, hpi_answers, extracted),
                llm_fallback_used=True,
                llm_error_message=error_message,
            )


intake_llm_service = IntakeLLMService()
