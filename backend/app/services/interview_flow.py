from enum import Enum
from typing import Dict, List
from pydantic import BaseModel


class InterviewStage(str, Enum):
    GREETING = "greeting"
    CHIEF_COMPLAINT = "chief_complaint"
    OPQRST = "opqrst"
    ASSOCIATED_SYMPTOMS = "associated_symptoms"
    PAST_MEDICAL_HISTORY = "past_medical_history"
    MEDICATIONS = "medications"
    ALLERGIES = "allergies"
    FAMILY_HISTORY = "family_history"
    SOCIAL_HISTORY = "social_history"
    REVIEW_OF_SYSTEMS = "review_of_systems"
    COMPLETION = "completion"


class StageConfig(BaseModel):
    name: str
    description: str
    required_info: List[str]
    sample_questions: List[str]
    min_exchanges: int


class InterviewFlowManager:

    def __init__(self):
        self.stages = self._initialize_stages()

    def _initialize_stages(self) -> Dict[InterviewStage, StageConfig]:

        return {

            InterviewStage.GREETING: StageConfig(
                name="Greeting",
                description="Start conversation",
                required_info=["main_problem"],
                sample_questions=[
                    "سلام، چه مشکلی دارید؟"
                ],
                min_exchanges=1
            ),

            InterviewStage.CHIEF_COMPLAINT: StageConfig(
                name="Chief Complaint",
                description="Main reason of visit",
                required_info=["chief_complaint"],
                sample_questions=[
                    "مشکل اصلی شما چیست؟",
                    "این مشکل از کی شروع شده؟"
                ],
                min_exchanges=2
            ),

            InterviewStage.OPQRST: StageConfig(
                name="OPQRST",
                description="Pain analysis",
                required_info=[
                    "onset",
                    "provocation",
                    "quality",
                    "radiation",
                    "severity",
                    "timing"
                ],
                sample_questions=[
                    "درد از چه زمانی شروع شد؟",
                    "چه چیزی بدترش می‌کند؟",
                    "شدت درد از ۱ تا ۱۰ چقدر است؟"
                ],
                min_exchanges=4
            ),

            InterviewStage.ASSOCIATED_SYMPTOMS: StageConfig(
                name="Associated Symptoms",
                description="Other symptoms",
                required_info=["associated_symptoms"],
                sample_questions=[
                    "علامت دیگری هم دارید؟"
                ],
                min_exchanges=2
            ),

            InterviewStage.PAST_MEDICAL_HISTORY: StageConfig(
                name="Past Medical History",
                description="Past diseases",
                required_info=["past_diseases", "surgeries"],
                sample_questions=[
                    "بیماری خاصی دارید؟",
                    "جراحی داشتید؟"
                ],
                min_exchanges=2
            ),

            InterviewStage.MEDICATIONS: StageConfig(
                name="Medications",
                description="Current medications",
                required_info=["medications"],
                sample_questions=[
                    "چه داروهایی مصرف می‌کنید؟"
                ],
                min_exchanges=1
            ),

            InterviewStage.ALLERGIES: StageConfig(
                name="Allergies",
                description="Drug allergies",
                required_info=["allergies"],
                sample_questions=[
                    "به دارویی حساسیت دارید؟"
                ],
                min_exchanges=1
            ),

            InterviewStage.FAMILY_HISTORY: StageConfig(
                name="Family History",
                description="Family diseases",
                required_info=["family_diseases"],
                sample_questions=[
                    "در خانواده بیماری خاصی وجود دارد؟"
                ],
                min_exchanges=1
            ),

            InterviewStage.SOCIAL_HISTORY: StageConfig(
                name="Social History",
                description="Lifestyle",
                required_info=["smoking", "alcohol", "occupation"],
                sample_questions=[
                    "سیگار مصرف می‌کنید؟"
                ],
                min_exchanges=1
            ),

            InterviewStage.REVIEW_OF_SYSTEMS: StageConfig(
                name="Review Of Systems",
                description="General review",
                required_info=["system_review"],
                sample_questions=[
                    "تب، تهوع یا کاهش وزن داشتید؟"
                ],
                min_exchanges=2
            ),

            InterviewStage.COMPLETION: StageConfig(
                name="Completion",
                description="Finish interview",
                required_info=[],
                sample_questions=[
                    "ممنون از همکاری شما."
                ],
                min_exchanges=1
            )
        }


flow_manager = InterviewFlowManager()
