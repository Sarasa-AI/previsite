"""Frozen orchestration inputs — not ClinicalContext; session/adapter signals only."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.workspace.domain.enums import ClinicalObjectId

SoapStatus = Literal["pending", "generating", "failed", "ready"]
VerificationStatus = Literal["verified", "partially_verified", "unverified"]


class ValidatedConflict(BaseModel):
    """Post-validation discrepancy signal (adapter-shaped; not ClinicalContext)."""

    model_config = ConfigDict(frozen=True)

    concept: str = ""
    confidence: Literal["high", "low"] = "high"
    involves_medication: bool = False


class ClinicalFindingSignal(BaseModel):
    """Adapter-shaped clinical finding signal (not ClinicalContext).

    Populated at the composition boundary from Clinical Intelligence outputs.
    """

    model_config = ConfigDict(frozen=True)

    finding_id: str = ""
    category: str = ""
    severity: str = ""
    title: str = ""
    confidence: Literal["high", "low", "unknown"] = "unknown"
    is_red_flag: bool = False
    is_conflict: bool = False
    is_risk: bool = False


class SessionState(BaseModel):
    """Session/runtime signals consumed by WorkspaceOrchestrator."""

    model_config = ConfigDict(frozen=True)

    soap_status: SoapStatus = "pending"
    verification_status: VerificationStatus | None = None
    offline: bool = False
    session_locked: bool = False
    soap_accepted: bool = False
    soap_exists: bool = False


class ReviewAcknowledgements(BaseModel):
    """Per-session review gates — never persisted on ClinicalContext.

    Extended fold fields (viewed/resolved/dismissed) are reconstructed from the
    Workflow Event Store and consumed by the next compute(); they never live
    inside WorkspacePlan / DTO shapes.
    """

    model_config = ConfigDict(frozen=True)

    acknowledged_objects: frozenset[ClinicalObjectId] = Field(default_factory=frozenset)
    viewed_objects: frozenset[ClinicalObjectId] = Field(default_factory=frozenset)
    resolved_objects: frozenset[ClinicalObjectId] = Field(default_factory=frozenset)
    dismissed_objects: frozenset[ClinicalObjectId] = Field(default_factory=frozenset)
    story_refresh_requested: bool = False
    story_frozen: bool = False


class OrchestratorInputs(BaseModel):
    """
    Adapter inputs not first-class on ClinicalContext.

    Red flags and patient questions live on Intake ClinicalSummary today;
    validated conflicts come from the SOAP validation path.
    """

    model_config = ConfigDict(frozen=True)

    red_flags: tuple[str, ...] = ()
    patient_questions: tuple[str, ...] = ()
    validated_conflicts: tuple[ValidatedConflict, ...] = ()
    clinical_findings: tuple[ClinicalFindingSignal, ...] = ()
    allergies_status_unknown: bool = False
    physician_edited_objects: frozenset[ClinicalObjectId] = Field(
        default_factory=frozenset
    )
    document_count: int = Field(default=0, ge=0)
