"""Finding repository protocol (no infrastructure imports)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from app.modules.intelligence.domain.models import (
    ClinicalFinding,
    Recommendation,
    RiskSignal,
)


class FindingRepositoryProtocol(Protocol):
    """Persistence port for Clinical Intelligence entities."""

    async def save_finding(self, finding: ClinicalFinding) -> ClinicalFinding:
        """Persist a finding; return the stored projection."""
        ...

    async def get_finding(self, finding_id: str) -> ClinicalFinding | None:
        """Return a finding by id, or None."""
        ...

    async def list_findings_for_session(
        self, session_id: int
    ) -> Sequence[ClinicalFinding]:
        """Return findings for a session ordered oldest → newest."""
        ...

    async def save_risk_signal(self, risk: RiskSignal) -> RiskSignal:
        ...

    async def list_risks_for_session(self, session_id: int) -> Sequence[RiskSignal]:
        ...

    async def save_recommendation(
        self, recommendation: Recommendation
    ) -> Recommendation:
        ...

    async def list_recommendations_for_session(
        self, session_id: int
    ) -> Sequence[Recommendation]:
        ...
