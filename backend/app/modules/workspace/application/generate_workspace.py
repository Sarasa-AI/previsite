"""GenerateWorkspaceUseCase — application entry for WorkspacePlan computation."""

from __future__ import annotations

from datetime import datetime

from app.modules.workspace.application.inputs import (
    OrchestratorInputs,
    ReviewAcknowledgements,
    SessionState,
)
from app.modules.workspace.application.workspace_orchestrator import (
    WorkspaceOrchestrator,
    workspace_orchestrator,
)
from app.modules.workspace.domain.enums import RoleProfile, SpecialtyLens
from app.modules.workspace.domain.models import WorkspacePlan
from app.schemas.clinical_context import ClinicalContext


class GenerateWorkspaceUseCase:
    """
    Application use case: produce a WorkspacePlan from clinical + session inputs.

    Thin wrapper over WorkspaceOrchestrator for future API / composition layers.
    """

    def __init__(self, orchestrator: WorkspaceOrchestrator | None = None) -> None:
        self._orchestrator = orchestrator or workspace_orchestrator

    def execute(
        self,
        context: ClinicalContext,
        *,
        session_state: SessionState | None = None,
        lens: SpecialtyLens = SpecialtyLens.GENERAL_MEDICINE,
        role: RoleProfile = RoleProfile.DOCTOR,
        review_state: ReviewAcknowledgements | None = None,
        inputs: OrchestratorInputs | None = None,
        now: datetime | None = None,
        include_trace: bool = True,
    ) -> WorkspacePlan:
        return self._orchestrator.compute(
            context,
            session_state=session_state,
            lens=lens,
            role=role,
            review_state=review_state,
            inputs=inputs,
            now=now,
            include_trace=include_trace,
        )


generate_workspace = GenerateWorkspaceUseCase()
