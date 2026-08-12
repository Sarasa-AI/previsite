"""Tests for interpreter validation-failure handling."""

from __future__ import annotations

import pytest
from unittest.mock import patch

from app.core.inference.domain.models import InferenceFinding
from app.modules.intelligence.application.interpreter import ArtifactInterpreter


SESSION_ID = 7


def _artifact(
    artifact_type: str = "clinical_finding",
    title: str = "Valid Title",
    summary: str = "Valid summary",
    confidence: float | None = 0.6,
    attributes: dict | None = None,
    finding_key: str = "key-valid",
) -> InferenceFinding:
    return InferenceFinding(
        artifact_type=artifact_type,
        finding_key=finding_key,
        title=title,
        summary=summary,
        confidence=confidence,
        attributes=attributes or {},
    )


class TestValidArtifactsProduceNoFailures:
    def setup_method(self):
        self.interpreter = ArtifactInterpreter()

    def test_valid_clinical_finding_no_failures(self):
        result = self.interpreter.interpret(SESSION_ID, [_artifact()])
        assert result.validation_failures == 0

    def test_valid_risk_signal_no_failures(self):
        result = self.interpreter.interpret(SESSION_ID, [_artifact(artifact_type="risk_signal")])
        assert result.validation_failures == 0

    def test_valid_recommendation_no_failures(self):
        result = self.interpreter.interpret(
            SESSION_ID, [_artifact(artifact_type="recommendation")]
        )
        assert result.validation_failures == 0

    def test_unknown_attribute_values_use_defaults_no_failures(self):
        # Invalid enum strings fall back to defaults — not validation failures
        artifact = _artifact(
            attributes={"category": "not_a_real_category", "severity": "not_a_real_severity"}
        )
        result = self.interpreter.interpret(SESSION_ID, [artifact])
        assert result.validation_failures == 0
        assert len(result.findings) == 1


class TestValidationFailureHandling:
    def setup_method(self):
        self.interpreter = ArtifactInterpreter()

    def test_failure_in_mapping_increments_counter(self):
        # Force the internal mapping method to raise, simulating a future
        # domain constraint violation.
        artifact = _artifact()
        with patch.object(
            self.interpreter,
            "_to_finding_command",
            side_effect=ValueError("Simulated mapping failure"),
        ):
            result = self.interpreter.interpret(SESSION_ID, [artifact])
        assert result.validation_failures == 1
        assert len(result.findings) == 0

    def test_failure_does_not_stop_remaining_artifacts(self):
        artifacts = [
            _artifact(finding_key="f1", title="Good 1"),
            _artifact(finding_key="f2", title="Will Fail"),
            _artifact(finding_key="f3", title="Good 2"),
        ]
        call_count = 0

        original = self.interpreter._to_finding_command

        def side_effect(session_id, artifact):
            nonlocal call_count
            call_count += 1
            if artifact.finding_key == "f2":
                raise ValueError("Simulated failure for f2")
            return original(session_id, artifact)

        with patch.object(self.interpreter, "_to_finding_command", side_effect=side_effect):
            result = self.interpreter.interpret(SESSION_ID, artifacts)

        assert result.validation_failures == 1
        assert len(result.findings) == 2
        assert call_count == 3  # all artifacts attempted

    def test_multiple_failures_counted_individually(self):
        artifacts = [_artifact(finding_key=f"f{i}", title=f"T{i}") for i in range(5)]
        with patch.object(
            self.interpreter,
            "_to_finding_command",
            side_effect=RuntimeError("Boom"),
        ):
            result = self.interpreter.interpret(SESSION_ID, artifacts)
        assert result.validation_failures == 5
        assert len(result.findings) == 0

    def test_validation_failures_do_not_affect_other_types(self):
        # If clinical_finding fails, risk_signal and recommendation should still succeed
        artifacts = [
            _artifact(artifact_type="clinical_finding", finding_key="f1", title="Bad Finding"),
            _artifact(artifact_type="risk_signal", finding_key="r1", title="Good Risk"),
        ]
        with patch.object(
            self.interpreter,
            "_to_finding_command",
            side_effect=ValueError("bad finding"),
        ):
            result = self.interpreter.interpret(SESSION_ID, artifacts)

        assert result.validation_failures == 1
        assert len(result.findings) == 0
        assert len(result.risk_signals) == 1
