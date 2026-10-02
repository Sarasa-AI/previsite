"""In-process metrics registry with Prometheus text exposition.

No external metrics dependency — scrapable via GET /metrics.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"

_DURATION_BUCKETS = (
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
    30.0,
    60.0,
    120.0,
    float("inf"),
)


def _labels_key(labels: dict[str, str]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted(labels.items()))


def _format_labels(labels: dict[str, str]) -> str:
    if not labels:
        return ""
    inner = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
    return "{" + inner + "}"


@dataclass
class _Counter:
    name: str
    help: str
    values: dict[tuple[tuple[str, str], ...], float] = field(default_factory=dict)

    def inc(self, labels: dict[str, str] | None = None, amount: float = 1.0) -> None:
        key = _labels_key(labels or {})
        self.values[key] = self.values.get(key, 0.0) + amount

    def render(self) -> list[str]:
        lines = [f"# HELP {self.name} {self.help}", f"# TYPE {self.name} counter"]
        if not self.values:
            lines.append(f"{self.name} 0")
            return lines
        for key, value in sorted(self.values.items()):
            labels = dict(key)
            lines.append(f"{self.name}{_format_labels(labels)} {value}")
        return lines


@dataclass
class _Histogram:
    name: str
    help: str
    buckets: tuple[float, ...]
    counts: dict[tuple[tuple[str, str], ...], list[float]] = field(default_factory=dict)
    sums: dict[tuple[tuple[str, str], ...], float] = field(default_factory=dict)
    totals: dict[tuple[tuple[str, str], ...], float] = field(default_factory=dict)

    def observe(self, value: float, labels: dict[str, str] | None = None) -> None:
        key = _labels_key(labels or {})
        if key not in self.counts:
            self.counts[key] = [0.0] * len(self.buckets)
            self.sums[key] = 0.0
            self.totals[key] = 0.0
        for i, bound in enumerate(self.buckets):
            if value <= bound:
                self.counts[key][i] += 1.0
        self.sums[key] += value
        self.totals[key] += 1.0

    def render(self) -> list[str]:
        lines = [f"# HELP {self.name} {self.help}", f"# TYPE {self.name} histogram"]
        if not self.counts:
            return lines
        for key in sorted(self.counts.keys()):
            labels = dict(key)
            cumulative = 0.0
            for bound, count in zip(self.buckets, self.counts[key]):
                cumulative += count
                bucket_labels = {**labels, "le": "+Inf" if bound == float("inf") else str(bound)}
                lines.append(f"{self.name}_bucket{_format_labels(bucket_labels)} {cumulative}")
            lines.append(f"{self.name}_sum{_format_labels(labels)} {self.sums[key]}")
            lines.append(f"{self.name}_count{_format_labels(labels)} {self.totals[key]}")
        return lines


class _MetricsRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.soap_generation_duration_seconds = _Histogram(
            "previsit_soap_generation_duration_seconds",
            "SOAP generation duration in seconds",
            _DURATION_BUCKETS,
        )
        self.clinical_context_build_duration_seconds = _Histogram(
            "previsit_clinical_context_build_duration_seconds",
            "ClinicalContext build duration in seconds",
            _DURATION_BUCKETS,
        )
        self.ocr_duration_seconds = _Histogram(
            "previsit_ocr_duration_seconds",
            "OCR extraction duration in seconds",
            _DURATION_BUCKETS,
        )
        self.summary_duration_seconds = _Histogram(
            "previsit_summary_duration_seconds",
            "Summary generation duration in seconds",
            _DURATION_BUCKETS,
        )
        self.rag_duration_seconds = _Histogram(
            "previsit_rag_duration_seconds",
            "RAG retrieval duration in seconds",
            _DURATION_BUCKETS,
        )
        self.pipeline_stage_duration_seconds = _Histogram(
            "previsit_pipeline_stage_duration_seconds",
            "Generic pipeline stage duration in seconds",
            _DURATION_BUCKETS,
        )
        self.soap_success_total = _Counter(
            "previsit_soap_success_total",
            "Successful SOAP generations",
        )
        self.soap_failure_total = _Counter(
            "previsit_soap_failure_total",
            "Failed SOAP generations",
        )
        self.pipeline_latency_seconds = _Histogram(
            "previsit_pipeline_latency_seconds",
            "End-to-end pipeline latency by entry point",
            _DURATION_BUCKETS,
        )
        self.llm_tokens_total = _Counter(
            "previsit_llm_tokens_total",
            "LLM token usage",
        )
        self.llm_estimated_cost_usd_total = _Counter(
            "previsit_llm_estimated_cost_usd_total",
            "Estimated LLM cost in USD",
        )

    def generate(self) -> bytes:
        with self._lock:
            parts: list[str] = []
            for metric in (
                self.soap_generation_duration_seconds,
                self.clinical_context_build_duration_seconds,
                self.ocr_duration_seconds,
                self.summary_duration_seconds,
                self.rag_duration_seconds,
                self.pipeline_stage_duration_seconds,
                self.soap_success_total,
                self.soap_failure_total,
                self.pipeline_latency_seconds,
                self.llm_tokens_total,
                self.llm_estimated_cost_usd_total,
            ):
                parts.extend(metric.render())
            return ("\n".join(parts) + "\n").encode("utf-8")

    def reset(self) -> None:
        """Test helper: clear all series."""
        with self._lock:
            for metric in (
                self.soap_generation_duration_seconds,
                self.clinical_context_build_duration_seconds,
                self.ocr_duration_seconds,
                self.summary_duration_seconds,
                self.rag_duration_seconds,
                self.pipeline_stage_duration_seconds,
                self.pipeline_latency_seconds,
            ):
                metric.counts.clear()
                metric.sums.clear()
                metric.totals.clear()
            for metric in (
                self.soap_success_total,
                self.soap_failure_total,
                self.llm_tokens_total,
                self.llm_estimated_cost_usd_total,
            ):
                metric.values.clear()


REGISTRY = _MetricsRegistry()


def observe_duration(stage: str, duration_ms: int, status: str) -> None:
    seconds = max(duration_ms, 0) / 1000.0
    with REGISTRY._lock:
        REGISTRY.pipeline_stage_duration_seconds.observe(
            seconds, {"stage": stage, "status": status}
        )
        if stage in ("soap.generate", "soap.pipeline"):
            REGISTRY.soap_generation_duration_seconds.observe(seconds, {"status": status})
        elif stage == "clinical_context.build":
            REGISTRY.clinical_context_build_duration_seconds.observe(
                seconds, {"status": status}
            )
        elif stage == "summary.build":
            REGISTRY.summary_duration_seconds.observe(seconds, {"status": status})
        elif stage == "rag.retrieve":
            REGISTRY.rag_duration_seconds.observe(seconds, {"status": status})


def observe_ocr_duration(duration_ms: int, status: str, ocr_type: str) -> None:
    seconds = max(duration_ms, 0) / 1000.0
    with REGISTRY._lock:
        REGISTRY.ocr_duration_seconds.observe(
            seconds, {"status": status, "ocr_type": ocr_type}
        )
    observe_duration("ocr.extract", duration_ms, status)


def inc_soap_success() -> None:
    with REGISTRY._lock:
        REGISTRY.soap_success_total.inc()


def inc_soap_failure(error_type: str = "unknown") -> None:
    with REGISTRY._lock:
        REGISTRY.soap_failure_total.inc({"error_type": error_type or "unknown"})


def observe_pipeline_latency(entry: str, duration_ms: int) -> None:
    with REGISTRY._lock:
        REGISTRY.pipeline_latency_seconds.observe(
            max(duration_ms, 0) / 1000.0, {"entry": entry}
        )


def observe_tokens(model: str | None, input_tokens: int | None, output_tokens: int | None) -> None:
    label = model or "unknown"
    with REGISTRY._lock:
        if input_tokens:
            REGISTRY.llm_tokens_total.inc(
                {"direction": "input", "model": label}, float(input_tokens)
            )
        if output_tokens:
            REGISTRY.llm_tokens_total.inc(
                {"direction": "output", "model": label}, float(output_tokens)
            )


def observe_cost(model: str | None, cost_usd: float | None) -> None:
    if cost_usd is None:
        return
    with REGISTRY._lock:
        REGISTRY.llm_estimated_cost_usd_total.inc(
            {"model": model or "unknown"}, float(cost_usd)
        )


def metrics_response() -> tuple[bytes, str]:
    return REGISTRY.generate(), CONTENT_TYPE_LATEST


def reset_metrics_for_tests() -> None:
    REGISTRY.reset()
