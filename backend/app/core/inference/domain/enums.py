"""Inference Runtime domain enumerations."""

from __future__ import annotations

from enum import Enum


class InferenceStatus(str, Enum):
    """Lifecycle status of an inference execution."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
