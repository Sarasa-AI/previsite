"""In-memory Finding repository — for unit / application tests."""

from __future__ import annotations

from collections.abc import Sequence

from app.modules.intelligence.domain.models import (
    ClinicalFinding,
    Recommendation,
    RiskSignal,
)


class InMemoryFindingRepository:
    """In-memory store implementing FindingRepositoryProtocol."""

    def __init__(self) -> None:
        self._findings: dict[str, ClinicalFinding] = {}
        self._risks: dict[str, RiskSignal] = {}
        self._recommendations: dict[str, Recommendation] = {}

    async def save_finding(self, finding: ClinicalFinding) -> ClinicalFinding:
        self._findings[finding.finding_id] = finding
        return finding

    async def get_finding(self, finding_id: str) -> ClinicalFinding | None:
        return self._findings.get(finding_id)

    async def list_findings_for_session(
        self, session_id: int
    ) -> Sequence[ClinicalFinding]:
        rows = [f for f in self._findings.values() if f.session_id == session_id]
        return tuple(sorted(rows, key=lambda f: f.created_at))

    async def save_risk_signal(self, risk: RiskSignal) -> RiskSignal:
        self._risks[risk.risk_id] = risk
        return risk

    async def list_risks_for_session(self, session_id: int) -> Sequence[RiskSignal]:
        rows = [r for r in self._risks.values() if r.session_id == session_id]
        return tuple(sorted(rows, key=lambda r: r.created_at))

    async def save_recommendation(
        self, recommendation: Recommendation
    ) -> Recommendation:
        self._recommendations[recommendation.recommendation_id] = recommendation
        return recommendation

    async def list_recommendations_for_session(
        self, session_id: int
    ) -> Sequence[Recommendation]:
        rows = [
            r
            for r in self._recommendations.values()
            if r.session_id == session_id
        ]
        return tuple(sorted(rows, key=lambda r: r.created_at))

    def clear(self) -> None:
        self._findings.clear()
        self._risks.clear()
        self._recommendations.clear()
