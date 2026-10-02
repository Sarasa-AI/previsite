"""Tests for unknown artifact type handling — forward compatibility guarantee."""

from __future__ import annotations

import pytest

from app.core.inference.domain.models import InferenceFinding
from app.modules.intelligence.application.interpreter import ArtifactInterpreter


SESSION_ID = 10


def _artifact(artifact_type: str, title: str = "Title", key: str = "k1") -> InferenceFinding:
    return InferenceFinding(
        artifact_type=artifact_type,
        finding_key=key,
        title=title,
        summary="Summary",
        confidence=0.5,
        attributes={},
    )


class TestUnknownArtifactTypes:
    def setup_method(self):
        self.interpreter = ArtifactInterpreter()

    def test_unknown_type_does_not_raise(self):
        result = self.interpreter.interpret(SESSION_ID, [_artifact("future_artifact_v3")])
        assert result.ignored_unknown == 1

    def test_unknown_type_produces_no_commands(self):
        result = self.interpreter.interpret(SESSION_ID, [_artifact("unknown_type")])
        assert result.findings == ()
        assert result.risk_signals == ()
        assert result.recommendations == ()

    def test_multiple_unknown_types_all_ignored(self):
        artifacts = [
            _artifact("type_a", key="k1"),
            _artifact("type_b", key="k2"),
            _artifact("type_c", key="k3"),
        ]
        result = self.interpreter.interpret(SESSION_ID, artifacts)
        assert result.ignored_unknown == 3
        assert result.validation_failures == 0

    def test_mixed_known_and_unknown(self):
        artifacts = [
            _artifact("clinical_finding", title="Known 1", key="k1"),
            _artifact("novel_ai_output", title="Unknown 1", key="k2"),
            _artifact("risk_signal", title="Known 2", key="k3"),
            _artifact("future_type_xyz", title="Unknown 2", key="k4"),
        ]
        result = self.interpreter.interpret(SESSION_ID, artifacts)
        assert len(result.findings) == 1
        assert len(result.risk_signals) == 1
        assert result.ignored_unknown == 2
        assert result.validation_failures == 0

    def test_uppercase_unknown_type_is_ignored(self):
        # artifact_type lookup is lower-cased
        result = self.interpreter.interpret(SESSION_ID, [_artifact("CLINICAL_FINDING_V2")])
        assert result.ignored_unknown == 1

    def test_empty_artifact_type_is_ignored(self):
        # InferenceFinding validates artifact_type is non-empty, but test the boundary
        # Using an unrecognised value that passes InferenceFinding validation
        result = self.interpreter.interpret(SESSION_ID, [_artifact("unrecognised")])
        assert result.ignored_unknown == 1

    def test_case_insensitive_known_types_still_work(self):
        # "Clinical_Finding" — lower-cased → "clinical_finding" → known
        artifact = InferenceFinding(
            artifact_type="Clinical_Finding",
            finding_key="cf-1",
            title="Hypertension",
            summary="Elevated BP",
            confidence=0.9,
            attributes={},
        )
        result = self.interpreter.interpret(SESSION_ID, [artifact])
        assert len(result.findings) == 1
        assert result.ignored_unknown == 0
