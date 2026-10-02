from enum import Enum


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
