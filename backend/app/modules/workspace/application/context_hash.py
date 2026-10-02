"""Deterministic ClinicalContext hashing for plan metadata (no mutation)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.schemas.clinical_context import ClinicalContext


def _stable(obj: Any) -> Any:
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, dict):
        return {k: _stable(obj[k]) for k in sorted(obj)}
    if isinstance(obj, (list, tuple)):
        return [_stable(x) for x in obj]
    if hasattr(obj, "model_dump"):
        return _stable(obj.model_dump(mode="json"))
    return str(obj)


def _stabilize_for_hash(payload: Any) -> Any:
    """Exclude derived / volatile clock fields from the clinical content hash.

    - ``timeline`` is rebuilt with ``anchor_at = now()`` on every build.
    - ``summary.extracted_at`` defaults to ``datetime.utcnow`` when the builder
      does not set it, so it changes between identical source facts.

    Meaningful clinical changes still alter summary content, overview, evidence,
    chat history, etc. Excluding clocks keeps plan_etag / If-Match stable.
    """
    if not isinstance(payload, dict):
        return payload
    out = dict(payload)
    out.pop("timeline", None)
    summary = out.get("summary")
    if isinstance(summary, dict):
        summary = dict(summary)
        summary.pop("extracted_at", None)
        out["summary"] = summary
    return out


def compute_context_hash(context: ClinicalContext) -> str:
    """SHA-256 hex digest of a stable ClinicalContext serialization."""
    payload = _stabilize_for_hash(_stable(context.model_dump(mode="json")))
    canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
