"""Clinical Intelligence domain enumerations."""

from __future__ import annotations

from enum import Enum


class FindingCategory(str, Enum):
    """Clinical finding category for signal routing."""

    RED_FLAG = "red_flag"
    CONFLICT = "conflict"
    RISK = "risk"
    OBSERVATION = "observation"
    MISSING_DATA = "missing_data"


class FindingSeverity(str, Enum):
    """Relative clinical urgency of a finding."""

    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"


class FindingSource(str, Enum):
    """Origin class of a finding — origin-agnostic for workflow."""

    RULE_ENGINE = "rule_engine"
    AI_RUNTIME = "ai_runtime"
    KNOWLEDGE_BASE = "knowledge_base"
    MANUAL = "manual"
    SYSTEM_DERIVED = "system_derived"


class RiskLevel(str, Enum):
    """Severity band for a risk signal."""

    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"


class RecommendationKind(str, Enum):
    """Recommendation type — no treatment engine this sprint."""

    FOLLOW_UP = "follow_up"
    REVIEW = "review"
    MONITOR = "monitor"
    INVESTIGATE = "investigate"
    OTHER = "other"


class RecommendationStatus(str, Enum):
    """Lightweight recommendation lifecycle readiness (no transition engine)."""

    ACTIVE = "active"
    SUPERSEDED = "superseded"
