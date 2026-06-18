import logging
import asyncio

from app.schemas.intake import ClinicalSummary, DemographicsInput, HPIQuestionsResponse
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

LAYER3_SYSTEM_PROMPT = """You are a clinical documentation assistant for physicians.
Your task is to convert patient-provided intake information into a concise clinician-facing summary.
The patient is Persian-speaking, but the output should use professional Persian medical terminology commonly used in clinical documentation.
Goals: Save physician time, Preserve clinical accuracy, Present information in a concise and organized format, Use medical terminology when appropriate, Convert lay language into physician-friendly language, Highlight clinically relevant positives and negatives.
Rules:
- Use only information provided in the input.
- Never invent symptoms, findings, diagnoses, or negative findings.
- Never infer diagnoses.
- Never suggest treatments.
- Never add information that was not explicitly stated by the patient.
- If information is missing, omit it.
- Preserve chronology and severity when available.
- Use concise physician-oriented language.
- Maintain a neutral clinical tone.
- Output valid JSON only.

JSON Output Schema:
{ "chief_complaint": "Brief physician-facing chief complaint.", "hpi_summary": "Concise narrative summary of the present illness.", "pertinent_positives": ["Important symptoms or findings reported"], "pertinent_negatives": ["Important symptoms specifically denied"], "red_flags": ["Potentially concerning findings explicitly reported"] }"""


def _build_layer2_user_prompt(demographics: DemographicsInput) -> str:
    return f"""Patient Information
Age: {demographics.age}
Sex: {demographics.sex}
Chief Complaint: {demographics.chief_complaint}
Generate the Present Illness questions."""


def _build_layer3_user_prompt(
    demographics: DemographicsInput,
    hpi_answers: dict[str, str],
) -> str:
    import json

    return f"""Patient Information
Age: {demographics.age}
Sex: {demographics.sex}
Chief Complaint: {demographics.chief_complaint}
Present Illness Answers: {json.dumps(hpi_answers, ensure_ascii=False)}
Generate a clinician-facing summary."""


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


def _fallback_clinical_summary(
    demographics: DemographicsInput,
    hpi_answers: dict[str, str],
) -> ClinicalSummary:
    """Build a basic clinician summary from patient answers when LLM is unavailable."""
    answer_parts = [f"{k}: {v}" for k, v in hpi_answers.items()]
    hpi_text = "؛ ".join(answer_parts) if answer_parts else "اطلاعات تکمیلی ثبت نشده است."

    return ClinicalSummary(
        chief_complaint=demographics.chief_complaint,
        hpi_summary=(
            f"بیمار {demographics.sex} {demographics.age} ساله با شکایت {demographics.chief_complaint} مراجعه کرده است. "
            f"{hpi_text}"
        ),
        pertinent_positives=list(hpi_answers.values()),
        pertinent_negatives=[],
        red_flags=[],
    )


class IntakeLLMService:
    async def generate_hpi_questions(self, demographics: DemographicsInput) -> HPIQuestionsResponse:
        user_prompt = _build_layer2_user_prompt(demographics)

        try:
            parsed = await asyncio.wait_for(
                openrouter_service.generate_json(
                    system_prompt=LAYER2_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                ),
                timeout=15.0
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

    async def generate_clinical_summary(
        self,
        demographics: DemographicsInput,
        hpi_answers: dict[str, str],
    ) -> ClinicalSummary:
        user_prompt = _build_layer3_user_prompt(demographics, hpi_answers)

        try:
            parsed = await asyncio.wait_for(
                openrouter_service.generate_json(
                    system_prompt=LAYER3_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                ),
                timeout=15.0
            )
            return ClinicalSummary.model_validate(parsed)
        except (OpenRouterServiceError, ValueError, TimeoutError) as exc:
            if isinstance(exc, TimeoutError):
                logger.warning("Layer 3 LLM fallback triggered: LLM response exceeded 15s SLA")
            else:
                logger.warning("Layer 3 LLM fallback triggered: %s", exc)
            return _fallback_clinical_summary(demographics, hpi_answers)


intake_llm_service = IntakeLLMService()
