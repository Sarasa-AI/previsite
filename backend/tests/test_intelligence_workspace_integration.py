"""Integration: finding creation → workspace signal generation."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.modules.intelligence.application.adapters.workspace_signals import (
    to_finding_signal_bundle,
)
from app.modules.intelligence.application.commands import CreateFindingCommand
from app.modules.intelligence.application.finding_service import FindingService
from app.modules.intelligence.application.in_memory import InMemoryFindingRepository
from app.modules.intelligence.domain.enums import (
    FindingCategory,
    FindingSeverity,
    FindingSource,
)
from app.modules.intelligence.domain.models import ConfidenceScore, Evidence
from app.modules.timeline.domain.enums import (
    ClinicalCategory,
    EventSource,
    EventType,
    TemporalKind,
    TemporalPrecision,
    TemporalStatus,
)
from app.modules.timeline.domain.models import (
    ClinicalTimeline,
    TemporalExpression,
    TimelineEvent,
)
from app.modules.workspace.application.compose_intelligence_signals import (
    orchestrator_inputs_from_finding_bundle,
)
from app.modules.workspace.application.inputs import OrchestratorInputs, SessionState
from app.modules.workspace.application.signals import extract_signals
from app.modules.workspace.application.workspace_orchestrator import WorkspaceOrchestrator
from app.modules.workspace.domain.enums import (
    AttentionSlot,
    ClinicalObjectId,
    PriorityLevel,
)
from app.schemas.clinical_context import ClinicalContext
from app.schemas.intake import MedicalOverview
from app.schemas.medical import MedicalSummary

FIXED_NOW = datetime(2026, 8, 4, 16, 0, 0, tzinfo=timezone.utc)
SESSION_ID = 99


def _context() -> ClinicalContext:
    event = TimelineEvent(
        event_id="e0",
        event_type=EventType.SYMPTOM_ONGOING,
        clinical_category=ClinicalCategory.SYMPTOM,
        label="Headache",
        temporal=TemporalExpression(
            kind=TemporalKind.RELATIVE_DURATION,
            raw_text="2 days",
            relative_value=2,
            relative_unit="days",
            precision=TemporalPrecision.DAY,
            uncertainty=False,
        ),
        status=TemporalStatus.ONGOING,
        source=EventSource.HPI,
    )
    return ClinicalContext(
        session_id=SESSION_ID,
        patient_id=1,
        summary=MedicalSummary(
            chief_complaint="Headache",
            extracted_at=FIXED_NOW,
        ),
        overview=MedicalOverview(),
        timeline=ClinicalTimeline(
            session_id=SESSION_ID,
            patient_id=1,
            anchor_at=FIXED_NOW,
            events=(event,),
        ),
    )


@pytest.mark.asyncio
async def test_finding_creation_to_workspace_red_flag_signal() -> None:
    service = FindingService(InMemoryFindingRepository())
    finding = await service.create_finding(
        CreateFindingCommand(
            session_id=SESSION_ID,
            category=FindingCategory.RED_FLAG,
            severity=FindingSeverity.CRITICAL,
            title="Chest pain",
            source=FindingSource.RULE_ENGINE,
            source_id="rule_execution_7",
            confidence=ConfidenceScore(value=0.92),
            evidence=(
                Evidence(
                    source="intake",
                    excerpt="Crushing chest pain",
                    confidence=ConfidenceScore(value=0.9),
                ),
            ),
            created_at=FIXED_NOW,
        )
    )

    findings = await service.list_findings_for_session(SESSION_ID)
    bundle = to_finding_signal_bundle(SESSION_ID, findings)
    assert len(bundle.findings) == 1
    assert bundle.findings[0].is_red_flag is True
    assert bundle.findings[0].finding_id == finding.finding_id

    inputs = orchestrator_inputs_from_finding_bundle(bundle)
    assert len(inputs.clinical_findings) == 1

    ctx = _context()
    signals = extract_signals(ctx, SessionState(), inputs)
    assert "Chest pain" in signals.red_flags

    plan = WorkspaceOrchestrator().compute(
        ctx,
        session_state=SessionState(
            soap_status="ready", soap_exists=True, verification_status="verified"
        ),
        inputs=inputs,
        now=FIXED_NOW,
    )
    by_id = {d.object_id: d for d in plan.layout_directives}
    red = by_id[ClinicalObjectId.RED_FLAGS]
    assert red.priority in {PriorityLevel.P0, PriorityLevel.P1}
    assert red.slot is not AttentionSlot.HIDDEN


@pytest.mark.asyncio
async def test_conflict_finding_drives_validated_conflict_signal() -> None:
    service = FindingService(InMemoryFindingRepository())
    await service.create_finding(
        CreateFindingCommand(
            session_id=SESSION_ID,
            category=FindingCategory.CONFLICT,
            severity=FindingSeverity.HIGH,
            title="Medication discrepancy",
            source=FindingSource.SYSTEM_DERIVED,
            confidence=ConfidenceScore(value=0.85),
            created_at=FIXED_NOW,
        )
    )
    bundle = to_finding_signal_bundle(
        SESSION_ID, await service.list_findings_for_session(SESSION_ID)
    )
    inputs = orchestrator_inputs_from_finding_bundle(
        bundle, base=OrchestratorInputs()
    )
    signals = extract_signals(_context(), SessionState(), inputs)
    assert any(c.concept == "Medication discrepancy" for c in signals.validated_conflicts)
    assert signals.has_high_confidence_conflict is True

    plan = WorkspaceOrchestrator().compute(
        _context(),
        session_state=SessionState(
            soap_status="ready", soap_exists=True, verification_status="verified"
        ),
        inputs=inputs,
        now=FIXED_NOW,
    )
    conflicts = next(
        d for d in plan.layout_directives if d.object_id is ClinicalObjectId.CONFLICTS
    )
    assert conflicts.priority is PriorityLevel.P0
    assert conflicts.slot is AttentionSlot.PIN
