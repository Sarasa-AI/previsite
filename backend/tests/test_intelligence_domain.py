"""Clinical Intelligence domain invariant tests (no application / API / DB)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.modules.intelligence.domain.enums import (
    FindingCategory,
    FindingSeverity,
    FindingSource,
    RecommendationKind,
    RecommendationStatus,
    RiskLevel,
)
from app.modules.intelligence.domain.models import (
    FINDING_SCHEMA_VERSION,
    ClinicalFinding,
    ConfidenceScore,
    Evidence,
    Recommendation,
    RiskSignal,
)

NOW = datetime(2026, 8, 4, 12, 0, 0, tzinfo=timezone.utc)


def _confidence(**overrides) -> ConfidenceScore:
    base: dict = {"value": 0.9}
    base.update(overrides)
    return ConfidenceScore(**base)


def _evidence(**overrides) -> Evidence:
    base: dict = {
        "source": "intake",
        "excerpt": "Patient reports chest pain",
        "confidence": _confidence(),
    }
    base.update(overrides)
    return Evidence(**base)


def _finding(**overrides) -> ClinicalFinding:
    base: dict = {
        "finding_id": "finding-1",
        "session_id": 42,
        "category": FindingCategory.RED_FLAG,
        "severity": FindingSeverity.HIGH,
        "title": "Chest pain",
        "source": FindingSource.RULE_ENGINE,
        "confidence": _confidence(),
        "evidence": (_evidence(),),
        "created_at": NOW,
    }
    base.update(overrides)
    return ClinicalFinding(**base)


def _risk(**overrides) -> RiskSignal:
    base: dict = {
        "risk_id": "risk-1",
        "session_id": 42,
        "risk_key": "cardiovascular_risk",
        "level": RiskLevel.HIGH,
        "title": "Elevated CV risk",
        "confidence": _confidence(),
        "created_at": NOW,
    }
    base.update(overrides)
    return RiskSignal(**base)


def _recommendation(**overrides) -> Recommendation:
    base: dict = {
        "recommendation_id": "rec-1",
        "session_id": 42,
        "kind": RecommendationKind.REVIEW,
        "title": "Review ECG",
        "status": RecommendationStatus.ACTIVE,
        "confidence": _confidence(),
        "created_at": NOW,
    }
    base.update(overrides)
    return Recommendation(**base)


# ── Immutability ─────────────────────────────────────────────────────────────


def test_models_are_frozen() -> None:
    finding = _finding()
    with pytest.raises(ValidationError):
        finding.title = "changed"  # type: ignore[misc]

    conf = _confidence()
    with pytest.raises(ValidationError):
        conf.value = 0.1  # type: ignore[misc]

    risk = _risk()
    with pytest.raises(ValidationError):
        risk.risk_key = "other"  # type: ignore[misc]

    rec = _recommendation()
    with pytest.raises(ValidationError):
        rec.status = RecommendationStatus.SUPERSEDED  # type: ignore[misc]


# ── ConfidenceScore ──────────────────────────────────────────────────────────


def test_confidence_accepts_unknown_and_bounds() -> None:
    assert ConfidenceScore(value="unknown").value == "unknown"
    assert ConfidenceScore(value=0.0).value == 0.0
    assert ConfidenceScore(value=1.0).value == 1.0


def test_confidence_rejects_out_of_range() -> None:
    with pytest.raises(ValidationError, match="confidence must be in"):
        ConfidenceScore(value=1.5)
    with pytest.raises(ValidationError, match="confidence must be in"):
        ConfidenceScore(value=-0.1)


# ── Evidence ─────────────────────────────────────────────────────────────────


def test_evidence_requires_non_empty_excerpt_and_source() -> None:
    with pytest.raises(ValidationError, match="excerpt must be non-empty"):
        _evidence(excerpt="   ")
    with pytest.raises(ValidationError, match="source must be non-empty"):
        _evidence(source="")


# ── ClinicalFinding ──────────────────────────────────────────────────────────


def test_finding_valid_minimal() -> None:
    finding = _finding(source_id=None, summary="")
    assert finding.schema_version == FINDING_SCHEMA_VERSION
    assert finding.source_id is None
    assert finding.category is FindingCategory.RED_FLAG


def test_finding_source_id_optional_and_normalized() -> None:
    finding = _finding(source_id="model_run_abc")
    assert finding.source_id == "model_run_abc"

    blank = _finding(source_id="   ")
    assert blank.source_id is None


def test_finding_rejects_empty_title_and_id() -> None:
    with pytest.raises(ValidationError, match="title must be non-empty"):
        _finding(title="")
    with pytest.raises(ValidationError, match="finding_id must be non-empty"):
        _finding(finding_id="  ")
    with pytest.raises(ValidationError, match="session_id must be positive"):
        _finding(session_id=0)


def test_finding_create_factory() -> None:
    finding = ClinicalFinding.create(
        session_id=7,
        category=FindingCategory.CONFLICT,
        severity=FindingSeverity.MODERATE,
        title="Med discrepancy",
        source=FindingSource.MANUAL,
        source_id="rule_execution_9",
        evidence=(_evidence(),),
        created_at=NOW,
    )
    assert finding.finding_id
    assert finding.source_id == "rule_execution_9"
    assert finding.created_at == NOW


# ── RiskSignal ───────────────────────────────────────────────────────────────


def test_risk_key_required_non_empty() -> None:
    risk = _risk(risk_key="renal_risk")
    assert risk.risk_key == "renal_risk"
    with pytest.raises(ValidationError, match="risk_key must be non-empty"):
        _risk(risk_key="  ")


def test_risk_create_factory() -> None:
    risk = RiskSignal.create(
        session_id=3,
        risk_key="infection_risk",
        level=RiskLevel.CRITICAL,
        title="Possible sepsis",
        finding_id="finding-1",
        created_at=NOW,
    )
    assert risk.risk_id
    assert risk.risk_key == "infection_risk"
    assert risk.finding_id == "finding-1"


# ── Recommendation ───────────────────────────────────────────────────────────


def test_recommendation_status_active_default_and_superseded() -> None:
    active = _recommendation()
    assert active.status is RecommendationStatus.ACTIVE

    superseded = _recommendation(status=RecommendationStatus.SUPERSEDED)
    assert superseded.status is RecommendationStatus.SUPERSEDED


def test_recommendation_create_defaults_active() -> None:
    rec = Recommendation.create(
        session_id=1,
        kind=RecommendationKind.MONITOR,
        title="Monitor BP",
        created_at=NOW,
    )
    assert rec.status is RecommendationStatus.ACTIVE
    assert rec.recommendation_id
