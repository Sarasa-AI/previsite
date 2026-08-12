"""Artifact interpreter — maps neutral InferenceFinding objects into
Clinical Intelligence domain commands.

Runtime never creates Intelligence entities. This module owns all mapping
logic: confidence, evidence, title, summary, severity, category, source,
and RecommendationStatus/RiskLevel/FindingCategory mapping.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from app.core.inference.domain.models import InferenceFinding
from app.modules.intelligence.application.commands import (
    CreateFindingCommand,
    CreateRecommendationCommand,
    CreateRiskSignalCommand,
)
from app.modules.intelligence.domain.enums import (
    FindingCategory,
    FindingSeverity,
    FindingSource,
    RecommendationKind,
    RecommendationStatus,
    RiskLevel,
)
from app.modules.intelligence.domain.models import ConfidenceScore, Evidence

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Attribute → enum look-up tables (lower-cased keys for safe mapping)
# ---------------------------------------------------------------------------

_CATEGORY_MAP: dict[str, FindingCategory] = {
    "red_flag": FindingCategory.RED_FLAG,
    "conflict": FindingCategory.CONFLICT,
    "risk": FindingCategory.RISK,
    "observation": FindingCategory.OBSERVATION,
    "missing_data": FindingCategory.MISSING_DATA,
}

_SEVERITY_MAP: dict[str, FindingSeverity] = {
    "critical": FindingSeverity.CRITICAL,
    "high": FindingSeverity.HIGH,
    "moderate": FindingSeverity.MODERATE,
    "low": FindingSeverity.LOW,
}

_RISK_LEVEL_MAP: dict[str, RiskLevel] = {
    "critical": RiskLevel.CRITICAL,
    "high": RiskLevel.HIGH,
    "moderate": RiskLevel.MODERATE,
    "low": RiskLevel.LOW,
}

_RECOMMENDATION_KIND_MAP: dict[str, RecommendationKind] = {
    "follow_up": RecommendationKind.FOLLOW_UP,
    "review": RecommendationKind.REVIEW,
    "monitor": RecommendationKind.MONITOR,
    "investigate": RecommendationKind.INVESTIGATE,
    "other": RecommendationKind.OTHER,
}

#: Artifact types this interpreter knows how to handle.
KNOWN_ARTIFACT_TYPES: frozenset[str] = frozenset(
    {"clinical_finding", "risk_signal", "recommendation"}
)


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InterpretedArtifacts:
    """Output of a single interpretation pass over an InferenceResult."""

    findings: tuple[CreateFindingCommand, ...]
    risk_signals: tuple[CreateRiskSignalCommand, ...]
    recommendations: tuple[CreateRecommendationCommand, ...]
    ignored_unknown: int
    validation_failures: int


# ---------------------------------------------------------------------------
# Interpreter
# ---------------------------------------------------------------------------


class ArtifactInterpreter:
    """Maps neutral InferenceFinding artifacts into Intelligence domain commands.

    Rules
    -----
    - ``artifact_type == "clinical_finding"``  → :class:`CreateFindingCommand`
    - ``artifact_type == "risk_signal"``        → :class:`CreateRiskSignalCommand`
    - ``artifact_type == "recommendation"``     → :class:`CreateRecommendationCommand`
    - Unknown artifact types are silently ignored (forward compatibility).
    - Any exception during individual artifact mapping is logged and counted
      as a *validation_failure*; remaining artifacts continue processing.

    The interpreter never persists anything.  All persistence is the
    Orchestrator's responsibility.
    """

    def interpret(
        self,
        session_id: int,
        findings: Sequence[InferenceFinding],
    ) -> InterpretedArtifacts:
        """Interpret *findings* and return command tuples grouped by artifact type."""
        finding_cmds: list[CreateFindingCommand] = []
        risk_cmds: list[CreateRiskSignalCommand] = []
        rec_cmds: list[CreateRecommendationCommand] = []
        ignored_unknown = 0
        validation_failures = 0

        for artifact in findings:
            artifact_type = artifact.artifact_type.lower()

            if artifact_type not in KNOWN_ARTIFACT_TYPES:
                logger.debug(
                    "Ignoring unknown artifact type %r (forward compatibility).",
                    artifact.artifact_type,
                )
                ignored_unknown += 1
                continue

            try:
                if artifact_type == "clinical_finding":
                    finding_cmds.append(self._to_finding_command(session_id, artifact))
                elif artifact_type == "risk_signal":
                    risk_cmds.append(self._to_risk_signal_command(session_id, artifact))
                elif artifact_type == "recommendation":
                    rec_cmds.append(self._to_recommendation_command(session_id, artifact))
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Validation failure for artifact %r (type=%r): %s",
                    artifact.finding_key,
                    artifact.artifact_type,
                    exc,
                )
                validation_failures += 1

        return InterpretedArtifacts(
            findings=tuple(finding_cmds),
            risk_signals=tuple(risk_cmds),
            recommendations=tuple(rec_cmds),
            ignored_unknown=ignored_unknown,
            validation_failures=validation_failures,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_confidence(artifact: InferenceFinding) -> ConfidenceScore:
        if artifact.confidence is None:
            return ConfidenceScore(value="unknown")
        return ConfidenceScore(value=artifact.confidence)

    @staticmethod
    def _build_evidence(artifact: InferenceFinding) -> tuple[Evidence, ...]:
        excerpt = artifact.summary.strip() or artifact.title
        return (
            Evidence(
                source=artifact.finding_key,
                excerpt=excerpt,
                confidence=ArtifactInterpreter._build_confidence(artifact),
            ),
        )

    @staticmethod
    def _map_category(attributes: dict) -> FindingCategory:
        raw = str(attributes.get("category", "")).lower()
        return _CATEGORY_MAP.get(raw, FindingCategory.OBSERVATION)

    @staticmethod
    def _map_severity(attributes: dict) -> FindingSeverity:
        raw = str(attributes.get("severity", "")).lower()
        return _SEVERITY_MAP.get(raw, FindingSeverity.MODERATE)

    @staticmethod
    def _map_risk_level(attributes: dict) -> RiskLevel:
        raw = str(attributes.get("level", "")).lower()
        return _RISK_LEVEL_MAP.get(raw, RiskLevel.MODERATE)

    @staticmethod
    def _map_recommendation_kind(attributes: dict) -> RecommendationKind:
        raw = str(attributes.get("kind", "")).lower()
        return _RECOMMENDATION_KIND_MAP.get(raw, RecommendationKind.OTHER)

    def _to_finding_command(
        self,
        session_id: int,
        artifact: InferenceFinding,
    ) -> CreateFindingCommand:
        return CreateFindingCommand(
            session_id=session_id,
            category=self._map_category(artifact.attributes),
            severity=self._map_severity(artifact.attributes),
            title=artifact.title,
            summary=artifact.summary,
            source=FindingSource.AI_RUNTIME,
            source_id=artifact.finding_key,
            confidence=self._build_confidence(artifact),
            evidence=self._build_evidence(artifact),
        )

    def _to_risk_signal_command(
        self,
        session_id: int,
        artifact: InferenceFinding,
    ) -> CreateRiskSignalCommand:
        finding_id = artifact.attributes.get("finding_id") or None
        if finding_id is not None:
            finding_id = str(finding_id)
        return CreateRiskSignalCommand(
            session_id=session_id,
            risk_key=artifact.finding_key,
            level=self._map_risk_level(artifact.attributes),
            title=artifact.title,
            finding_id=finding_id,
            confidence=self._build_confidence(artifact),
            evidence=self._build_evidence(artifact),
        )

    def _to_recommendation_command(
        self,
        session_id: int,
        artifact: InferenceFinding,
    ) -> CreateRecommendationCommand:
        finding_id = artifact.attributes.get("finding_id") or None
        if finding_id is not None:
            finding_id = str(finding_id)
        return CreateRecommendationCommand(
            session_id=session_id,
            kind=self._map_recommendation_kind(artifact.attributes),
            title=artifact.title,
            rationale=artifact.summary,
            status=RecommendationStatus.ACTIVE,
            finding_id=finding_id,
            confidence=self._build_confidence(artifact),
            evidence=self._build_evidence(artifact),
        )
