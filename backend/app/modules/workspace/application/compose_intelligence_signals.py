"""Compose Clinical Intelligence signal bundles into OrchestratorInputs.

Workspace may import Intelligence adapter outputs (consumption direction only).
Intelligence must never import Workspace.
"""

from __future__ import annotations

from app.modules.intelligence.application.adapters.workspace_signals import (
    FindingSignalBundle,
)
from app.modules.workspace.application.inputs import (
    ClinicalFindingSignal,
    OrchestratorInputs,
)


def clinical_finding_signals_from_bundle(
    bundle: FindingSignalBundle,
) -> tuple[ClinicalFindingSignal, ...]:
    return tuple(
        ClinicalFindingSignal(
            finding_id=record.finding_id,
            category=record.category,
            severity=record.severity,
            title=record.title,
            confidence=record.confidence,
            is_red_flag=record.is_red_flag,
            is_conflict=record.is_conflict,
            is_risk=record.is_risk,
        )
        for record in bundle.findings
    )


def orchestrator_inputs_from_finding_bundle(
    bundle: FindingSignalBundle,
    *,
    base: OrchestratorInputs | None = None,
) -> OrchestratorInputs:
    """Attach finding signals to OrchestratorInputs.

    Mapping into ``red_flags`` / ``validated_conflicts`` happens in
    ``extract_signals`` so signal fold logic stays in one place.
    """
    base = base or OrchestratorInputs()
    signals = clinical_finding_signals_from_bundle(bundle)
    return base.model_copy(
        update={"clinical_findings": (*base.clinical_findings, *signals)}
    )
