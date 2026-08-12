"""Workspace domain enumerations (orchestration catalog)."""

from __future__ import annotations

from enum import Enum


class ClinicalObjectId(str, Enum):
    """Stable identifier for a workspace card or attention target."""

    CHIEF_COMPLAINT = "chief_complaint"
    RED_FLAGS = "red_flags"
    CRITICAL_ALERTS = "critical_alerts"
    CONFLICTS = "conflicts"
    ALLERGIES = "allergies"
    TIMELINE = "timeline"
    STORY = "story"
    LABS = "labs"
    CRITICAL_LABS = "critical_labs"
    MEDICATIONS = "medications"
    PMH = "pmh"
    DOCUMENTS = "documents"
    PATIENT_QUESTIONS = "patient_questions"
    MISSING_DATA = "missing_data"
    SOAP = "soap"
    SNAPSHOT = "snapshot"


class PriorityLevel(str, Enum):
    """Objective urgency tier assigned to every ClinicalObjectId."""

    P0 = "p0"
    P1 = "p1"
    P2 = "p2"
    P3 = "p3"


class AttentionSlot(str, Enum):
    """Where an object sits in the physician's attention field."""

    PIN = "pin"
    PRIMARY = "primary"
    SECONDARY = "secondary"
    DEFERRED = "deferred"
    HIDDEN = "hidden"


class SizeHint(str, Enum):
    """Viewport attention budget (abstract units, not pixels)."""

    EXPANDED = "expanded"
    STANDARD = "standard"
    COMPRESSED = "compressed"
    BADGE = "badge"


class TrustProvenance(str, Enum):
    """Clinical provenance tag on every card."""

    AI_GENERATED = "ai_generated"
    PATIENT_REPORTED = "patient_reported"
    DOCUMENT_OCR = "document_ocr"
    SYSTEM_DERIVED = "system_derived"
    PHYSICIAN_EDITED = "physician_edited"


class TrustVerification(str, Enum):
    """Verification state for trust descriptor."""

    VERIFIED = "verified"
    PARTIALLY_VERIFIED = "partially_verified"
    UNVERIFIED = "unverified"
    NA = "n/a"


class VisibilityReason(str, Enum):
    """Why an object is hidden — explainability only; never changes priority."""

    NO_DATA = "no_data"
    SPECIALTY_FILTER = "specialty_filter"
    COGNITIVE_BUDGET = "cognitive_budget"
    PHYSICIAN_DISMISSED = "physician_dismissed"
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"
    GENERATION_FAILED = "generation_failed"


class SpecialtyLens(str, Enum):
    """Named weight overlay; never changes layout structure or hides P0 objects."""

    GENERAL_MEDICINE = "general_medicine"
    ENDOCRINOLOGY = "endocrinology"
    CARDIOLOGY = "cardiology"
    NEUROLOGY = "neurology"
    FAMILY_MEDICINE = "family_medicine"


class RoleProfile(str, Enum):
    """Named orchestration profile for workspace variants."""

    DOCTOR = "doctor"
    RESIDENT = "resident"
    NURSE = "nurse"
    EMERGENCY = "emergency"
    TELEHEALTH = "telehealth"


class ReasonCode(str, Enum):
    """Decision queue reason code."""

    SAFETY = "SAFETY"
    ORIENT = "ORIENT"
    EVIDENCE = "EVIDENCE"
    OPEN_LOOP = "OPEN_LOOP"
    DOCUMENT = "DOCUMENT"


class WorkspaceState(str, Enum):
    """Computed workspace state machine value."""

    LOADING = "loading"
    GENERATING = "generating"
    VERIFIED = "verified"
    PARTIALLY_VERIFIED = "partially_verified"
    CONFLICT_PRESENT = "conflict_present"
    REVIEW_NEEDED = "review_needed"
    COMPLETED = "completed"
    READ_ONLY = "read_only"
    OFFLINE = "offline"
