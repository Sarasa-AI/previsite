"""Anti-corruption projection: ClinicalFinding → workspace-oriented signal bundle.

This module must not import Workspace packages. Workspace maps the bundle into
``OrchestratorInputs`` at the composition boundary.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.modules.intelligence.domain.enums import FindingCategory, FindingSeverity
from app.modules.intelligence.domain.models import ClinicalFinding, ConfidenceScore

ConfidenceBand = Literal["high", "low", "unknown"]


class FindingSignalRecord(BaseModel):
    """Neutral finding signal for Workspace consumption."""

    model_config = ConfigDict(frozen=True)

    finding_id: str
    category: str
    severity: str
    title: str
    confidence: ConfidenceBand
    is_red_flag: bool = False
    is_conflict: bool = False
    is_risk: bool = False


class FindingSignalBundle(BaseModel):
    """Session-scoped projection of findings for orchestration inputs."""

    model_config = ConfigDict(frozen=True)

    session_id: int
    findings: tuple[FindingSignalRecord, ...] = ()


def _confidence_band(score: ConfidenceScore) -> ConfidenceBand:
    if score.value == "unknown":
        return "unknown"
    return "high" if float(score.value) >= 0.7 else "low"


def to_finding_signal_record(finding: ClinicalFinding) -> FindingSignalRecord:
    category = finding.category
    return FindingSignalRecord(
        finding_id=finding.finding_id,
        category=category.value,
        severity=finding.severity.value,
        title=finding.title.strip(),
        confidence=_confidence_band(finding.confidence),
        is_red_flag=category is FindingCategory.RED_FLAG
        or finding.severity is FindingSeverity.CRITICAL,
        is_conflict=category is FindingCategory.CONFLICT,
        is_risk=category is FindingCategory.RISK,
    )


def to_finding_signal_bundle(
    session_id: int,
    findings: Sequence[ClinicalFinding],
) -> FindingSignalBundle:
    """Project domain findings into a Workspace-consumable signal bundle."""
    records = tuple(
        to_finding_signal_record(f)
        for f in findings
        if f.session_id == session_id and f.title.strip()
    )
    return FindingSignalBundle(session_id=session_id, findings=records)
