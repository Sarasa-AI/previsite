"""Tests for ArtifactInterpreter — artifact mapping to Intelligence commands."""

from __future__ import annotations

import pytest

from app.core.inference.domain.models import InferenceFinding
from app.modules.intelligence.application.commands import (
    CreateFindingCommand,
    CreateRecommendationCommand,
    CreateRiskSignalCommand,
)
from app.modules.intelligence.application.interpreter import (
    ArtifactInterpreter,
    KNOWN_ARTIFACT_TYPES,
)
from app.modules.intelligence.domain.enums import (
    FindingCategory,
    FindingSeverity,
    FindingSource,
    RecommendationKind,
    RecommendationStatus,
    RiskLevel,
)
from app.modules.intelligence.domain.models import ConfidenceScore


SESSION_ID = 42


def _finding(
    artifact_type: str = "clinical_finding",
    title: str = "Test Finding",
    summary: str = "Test summary",
    confidence: float | None = 0.8,
    attributes: dict | None = None,
    finding_key: str = "key-001",
) -> InferenceFinding:
    return InferenceFinding(
        artifact_type=artifact_type,
        finding_key=finding_key,
        title=title,
        summary=summary,
        confidence=confidence,
        attributes=attributes or {},
    )


class TestKnownArtifactTypes:
    def test_known_set_contents(self):
        assert "clinical_finding" in KNOWN_ARTIFACT_TYPES
        assert "risk_signal" in KNOWN_ARTIFACT_TYPES
        assert "recommendation" in KNOWN_ARTIFACT_TYPES

    def test_known_set_is_frozen(self):
        with pytest.raises((TypeError, AttributeError)):
            KNOWN_ARTIFACT_TYPES.add("new_type")  # type: ignore[attr-defined]


class TestClinicalFindingMapping:
    def setup_method(self):
        self.interpreter = ArtifactInterpreter()

    def test_clinical_finding_produces_finding_command(self):
        result = self.interpreter.interpret(SESSION_ID, [_finding()])
        assert len(result.findings) == 1
        assert len(result.risk_signals) == 0
        assert len(result.recommendations) == 0

    def test_finding_command_session_id(self):
        result = self.interpreter.interpret(SESSION_ID, [_finding()])
        assert result.findings[0].session_id == SESSION_ID

    def test_finding_command_title_and_summary(self):
        artifact = _finding(title="Chest pain", summary="Patient reports chest pain")
        result = self.interpreter.interpret(SESSION_ID, [artifact])
        cmd = result.findings[0]
        assert cmd.title == "Chest pain"
        assert cmd.summary == "Patient reports chest pain"

    def test_finding_command_source_is_ai_runtime(self):
        result = self.interpreter.interpret(SESSION_ID, [_finding()])
        assert result.findings[0].source == FindingSource.AI_RUNTIME

    def test_finding_command_source_id_is_finding_key(self):
        artifact = _finding(finding_key="abc-123")
        result = self.interpreter.interpret(SESSION_ID, [artifact])
        assert result.findings[0].source_id == "abc-123"

    def test_finding_command_confidence_numeric(self):
        artifact = _finding(confidence=0.75)
        result = self.interpreter.interpret(SESSION_ID, [artifact])
        assert result.findings[0].confidence == ConfidenceScore(value=0.75)

    def test_finding_command_confidence_none_becomes_unknown(self):
        artifact = _finding(confidence=None)
        result = self.interpreter.interpret(SESSION_ID, [artifact])
        assert result.findings[0].confidence == ConfidenceScore(value="unknown")

    def test_finding_command_evidence_excerpt_uses_summary(self):
        artifact = _finding(summary="Detailed excerpt here")
        result = self.interpreter.interpret(SESSION_ID, [artifact])
        assert result.findings[0].evidence[0].excerpt == "Detailed excerpt here"

    def test_finding_command_evidence_falls_back_to_title_when_summary_blank(self):
        artifact = _finding(title="Important finding", summary="   ")
        result = self.interpreter.interpret(SESSION_ID, [artifact])
        assert result.findings[0].evidence[0].excerpt == "Important finding"

    def test_finding_command_evidence_source_is_finding_key(self):
        artifact = _finding(finding_key="ev-key")
        result = self.interpreter.interpret(SESSION_ID, [artifact])
        assert result.findings[0].evidence[0].source == "ev-key"

    def test_finding_category_mapped_from_attributes(self):
        for attr_val, expected in [
            ("red_flag", FindingCategory.RED_FLAG),
            ("conflict", FindingCategory.CONFLICT),
            ("risk", FindingCategory.RISK),
            ("observation", FindingCategory.OBSERVATION),
            ("missing_data", FindingCategory.MISSING_DATA),
        ]:
            artifact = _finding(attributes={"category": attr_val})
            result = self.interpreter.interpret(SESSION_ID, [artifact])
            assert result.findings[0].category == expected, f"failed for {attr_val}"

    def test_finding_category_defaults_to_observation(self):
        artifact = _finding(attributes={})
        result = self.interpreter.interpret(SESSION_ID, [artifact])
        assert result.findings[0].category == FindingCategory.OBSERVATION

    def test_finding_severity_mapped_from_attributes(self):
        for attr_val, expected in [
            ("critical", FindingSeverity.CRITICAL),
            ("high", FindingSeverity.HIGH),
            ("moderate", FindingSeverity.MODERATE),
            ("low", FindingSeverity.LOW),
        ]:
            artifact = _finding(attributes={"severity": attr_val})
            result = self.interpreter.interpret(SESSION_ID, [artifact])
            assert result.findings[0].severity == expected

    def test_finding_severity_defaults_to_moderate(self):
        artifact = _finding(attributes={})
        result = self.interpreter.interpret(SESSION_ID, [artifact])
        assert result.findings[0].severity == FindingSeverity.MODERATE


class TestRiskSignalMapping:
    def setup_method(self):
        self.interpreter = ArtifactInterpreter()

    def _risk(self, **kwargs) -> InferenceFinding:
        return _finding(artifact_type="risk_signal", **kwargs)

    def test_risk_signal_produces_risk_command(self):
        result = self.interpreter.interpret(SESSION_ID, [self._risk()])
        assert len(result.risk_signals) == 1
        assert len(result.findings) == 0

    def test_risk_key_is_finding_key(self):
        artifact = self._risk(finding_key="risk-key-007")
        result = self.interpreter.interpret(SESSION_ID, [artifact])
        assert result.risk_signals[0].risk_key == "risk-key-007"

    def test_risk_level_mapped_from_attributes(self):
        for attr_val, expected in [
            ("critical", RiskLevel.CRITICAL),
            ("high", RiskLevel.HIGH),
            ("moderate", RiskLevel.MODERATE),
            ("low", RiskLevel.LOW),
        ]:
            artifact = self._risk(attributes={"level": attr_val})
            result = self.interpreter.interpret(SESSION_ID, [artifact])
            assert result.risk_signals[0].level == expected

    def test_risk_level_defaults_to_moderate(self):
        result = self.interpreter.interpret(SESSION_ID, [self._risk(attributes={})])
        assert result.risk_signals[0].level == RiskLevel.MODERATE

    def test_risk_finding_id_from_attributes(self):
        artifact = self._risk(attributes={"finding_id": "f-uuid-xyz"})
        result = self.interpreter.interpret(SESSION_ID, [artifact])
        assert result.risk_signals[0].finding_id == "f-uuid-xyz"

    def test_risk_finding_id_none_when_absent(self):
        result = self.interpreter.interpret(SESSION_ID, [self._risk(attributes={})])
        assert result.risk_signals[0].finding_id is None


class TestRecommendationMapping:
    def setup_method(self):
        self.interpreter = ArtifactInterpreter()

    def _rec(self, **kwargs) -> InferenceFinding:
        return _finding(artifact_type="recommendation", **kwargs)

    def test_recommendation_produces_rec_command(self):
        result = self.interpreter.interpret(SESSION_ID, [self._rec()])
        assert len(result.recommendations) == 1
        assert len(result.findings) == 0

    def test_recommendation_status_is_active(self):
        result = self.interpreter.interpret(SESSION_ID, [self._rec()])
        assert result.recommendations[0].status == RecommendationStatus.ACTIVE

    def test_recommendation_rationale_is_summary(self):
        artifact = self._rec(summary="Follow-up in 2 weeks")
        result = self.interpreter.interpret(SESSION_ID, [artifact])
        assert result.recommendations[0].rationale == "Follow-up in 2 weeks"

    def test_recommendation_kind_mapped_from_attributes(self):
        for attr_val, expected in [
            ("follow_up", RecommendationKind.FOLLOW_UP),
            ("review", RecommendationKind.REVIEW),
            ("monitor", RecommendationKind.MONITOR),
            ("investigate", RecommendationKind.INVESTIGATE),
            ("other", RecommendationKind.OTHER),
        ]:
            artifact = self._rec(attributes={"kind": attr_val})
            result = self.interpreter.interpret(SESSION_ID, [artifact])
            assert result.recommendations[0].kind == expected

    def test_recommendation_kind_defaults_to_other(self):
        result = self.interpreter.interpret(SESSION_ID, [self._rec(attributes={})])
        assert result.recommendations[0].kind == RecommendationKind.OTHER

    def test_recommendation_finding_id_from_attributes(self):
        artifact = self._rec(attributes={"finding_id": "find-abc"})
        result = self.interpreter.interpret(SESSION_ID, [artifact])
        assert result.recommendations[0].finding_id == "find-abc"


class TestMixedArtifacts:
    def setup_method(self):
        self.interpreter = ArtifactInterpreter()

    def test_multiple_artifact_types_routed_correctly(self):
        artifacts = [
            _finding(artifact_type="clinical_finding", finding_key="f1", title="Finding 1"),
            _finding(artifact_type="risk_signal", finding_key="r1", title="Risk 1"),
            _finding(artifact_type="recommendation", finding_key="rec1", title="Rec 1"),
        ]
        result = self.interpreter.interpret(SESSION_ID, artifacts)
        assert len(result.findings) == 1
        assert len(result.risk_signals) == 1
        assert len(result.recommendations) == 1

    def test_counts_are_zero_for_empty_input(self):
        result = self.interpreter.interpret(SESSION_ID, [])
        assert result.findings == ()
        assert result.risk_signals == ()
        assert result.recommendations == ()
        assert result.ignored_unknown == 0
        assert result.validation_failures == 0

    def test_multiple_same_type(self):
        artifacts = [
            _finding(finding_key="f1", title="Finding 1"),
            _finding(finding_key="f2", title="Finding 2"),
            _finding(finding_key="f3", title="Finding 3"),
        ]
        result = self.interpreter.interpret(SESSION_ID, artifacts)
        assert len(result.findings) == 3
