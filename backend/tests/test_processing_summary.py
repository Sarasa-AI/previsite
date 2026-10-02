"""Tests for ProcessingSummary immutability and field semantics."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.intelligence.application.orchestrator import ProcessingSummary


def _summary(**overrides) -> ProcessingSummary:
    defaults = dict(
        execution_id="exec-001",
        processed_count=5,
        created_findings=2,
        created_risks=1,
        created_recommendations=1,
        ignored_unknown=1,
        validation_failures=0,
    )
    defaults.update(overrides)
    return ProcessingSummary(**defaults)


class TestProcessingSummaryImmutability:
    def test_frozen_model(self):
        summary = _summary()
        with pytest.raises((ValidationError, TypeError)):
            summary.processed_count = 99  # type: ignore[misc]

    def test_frozen_model_cannot_add_field(self):
        summary = _summary()
        with pytest.raises((ValidationError, TypeError)):
            summary.extra_field = "extra"  # type: ignore[attr-defined]


class TestProcessingSummaryFields:
    def test_execution_id_stored(self):
        s = _summary(execution_id="run-xyz-123")
        assert s.execution_id == "run-xyz-123"

    def test_processed_count_equals_sum_of_all_categories(self):
        s = _summary(
            processed_count=7,
            created_findings=2,
            created_risks=2,
            created_recommendations=1,
            ignored_unknown=1,
            validation_failures=1,
        )
        total = (
            s.created_findings
            + s.created_risks
            + s.created_recommendations
            + s.ignored_unknown
            + s.validation_failures
        )
        assert s.processed_count == total

    def test_all_zero_counts(self):
        s = _summary(
            processed_count=0,
            created_findings=0,
            created_risks=0,
            created_recommendations=0,
            ignored_unknown=0,
            validation_failures=0,
        )
        assert s.processed_count == 0

    def test_only_findings(self):
        s = _summary(
            processed_count=3,
            created_findings=3,
            created_risks=0,
            created_recommendations=0,
            ignored_unknown=0,
            validation_failures=0,
        )
        assert s.created_findings == 3
        assert s.created_risks == 0

    def test_only_ignored(self):
        s = _summary(
            processed_count=4,
            created_findings=0,
            created_risks=0,
            created_recommendations=0,
            ignored_unknown=4,
            validation_failures=0,
        )
        assert s.ignored_unknown == 4

    def test_validation_failures_tracked(self):
        s = _summary(
            processed_count=2,
            created_findings=0,
            created_risks=0,
            created_recommendations=0,
            ignored_unknown=0,
            validation_failures=2,
        )
        assert s.validation_failures == 2
