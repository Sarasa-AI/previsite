from typing import Optional
from app.services.interview_flow import InterviewStage
from app.schemas.medical import MedicalSummary


class InterviewController:

    def detect_stage(self, summary: Optional[MedicalSummary], message_count: int) -> InterviewStage:
        """
        تعیین مرحله مصاحبه بر اساس داده‌های استخراج شده و تعداد پیام‌ها
        """
        if not summary:
            return InterviewStage.CHIEF_COMPLAINT

        # 1. Chief Complaint & Initial details
        if not summary.chief_complaint or not summary.symptom_duration:
            if message_count < 4:
                return InterviewStage.CHIEF_COMPLAINT

        # 2. OPQRST / Detailed Symptoms
        if not summary.symptoms or not summary.symptom_severity:
            if message_count < 8:
                return InterviewStage.OPQRST

        # 3. Associated Symptoms / Review of Systems
        if not summary.review_of_systems:
            if message_count < 12:
                return InterviewStage.ASSOCIATED_SYMPTOMS

        # 4. Past Medical History
        if not summary.past_medical_history and message_count < 15:
            return InterviewStage.PAST_MEDICAL_HISTORY

        # 5. Medications & Allergies
        if not summary.current_medications or not summary.allergies:
            if message_count < 18:
                return InterviewStage.MEDICATIONS

        # 6. Social History
        if not summary.smoking_status and message_count < 21:
            return InterviewStage.SOCIAL_HISTORY

        return InterviewStage.COMPLETION

    def get_stage_instruction(self, stage: InterviewStage) -> str:

        instructions = {

            InterviewStage.CHIEF_COMPLAINT: """
تمرکز روی مشکل اصلی بیمار.
باید بفهمی:
- مشکل اصلی چیست
- از چه زمانی شروع شده
""",

            InterviewStage.OPQRST: """
علائم را با روش OPQRST بررسی کن:

O - onset (شروع)
P - provocation (چه چیزی بدتر/بهتر می‌کند)
Q - quality (نوع درد)
R - radiation (انتشار)
S - severity (شدت)
T - timing (مدت)
""",

            InterviewStage.ASSOCIATED_SYMPTOMS: """
علائم همراه را بررسی کن.
مثلاً:
تب، تهوع، ضعف، سرگیجه
""",

            InterviewStage.PAST_MEDICAL_HISTORY: """
سابقه پزشکی بیمار را بپرس:
- بیماری‌های مزمن
- جراحی‌ها
- بستری شدن
""",

            InterviewStage.MEDICATIONS: """
داروهای فعلی بیمار را بپرس.
""",

            InterviewStage.ALLERGIES: """
آلرژی دارویی یا غذایی.
""",

            InterviewStage.FAMILY_HISTORY: """
سابقه بیماری در خانواده.
""",

            InterviewStage.SOCIAL_HISTORY: """
سبک زندگی:
- سیگار
- الکل
- شغل
""",

            InterviewStage.COMPLETION: """
اگر اطلاعات کافی جمع شد گفتگو را جمع‌بندی کن.
"""
        }

        return instructions.get(stage, "")


interview_controller = InterviewController()
