#!/usr/bin/env python3
"""Benchmark OpenRouter chat models for SOAP note generation latency.

Discovers the fastest available models at runtime via OpenRouter's live catalog
(sorted server-side by throughput), then measures median TTFT and TPS per model.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import statistics
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import httpx
from dotenv import load_dotenv
from openai import AsyncOpenAI

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Load environment variables BEFORE importing settings
load_dotenv(BACKEND_ROOT / ".env")

from app.core.config import settings  # noqa: E402
from app.schemas.medical import MedicalSummary  # noqa: E402
from app.schemas.pmh import PMHAnswer  # noqa: E402
from app.services.pmh_service import format_pmh_for_prompt  # noqa: E402
from app.services.soap_generator import SOAPNoteGenerator  # noqa: E402

# --- Tunable constants (no magic numbers in logic) ---
MAX_MODELS = 100
MAX_CONCURRENT_REQUESTS = 2
BATCH_DELAY_SECONDS = 1.5
COMPLETION_TIMEOUT_SECONDS = 15.0
RUNS_PER_MODEL = 3
RETRY_COUNT = 0
TEMPERATURE = 0.2
MAX_COMPLETION_TOKENS = 2500
MODELS_API_TIMEOUT_SECONDS = 60.0
HTTP_CLIENT_BUFFER_SECONDS = 5.0

OPENROUTER_MODELS_URL = (
    "https://openrouter.ai/api/v1/models?sort=throughput-high-to-low&output_modalities=text"
)

RESULTS_DIR = Path(__file__).resolve().parent / "benchmark_results"

PMH_DATE_VALUE = "1398"


@dataclass(frozen=True)
class DiscoveredModel:
    slug: str
    provider: str
    pricing_tier: str
    prompt_price_per_million: float | None
    reported_throughput: float | None
    sort_rank: int


@dataclass
class CompletionRun:
    status: str
    ttft_ms: float | None
    tps: float | None
    error: str | None = None


@dataclass
class ModelBenchmarkResult:
    model: DiscoveredModel
    median_ttft_ms: float | None
    median_tps: float | None
    error_count: int
    runs: list[CompletionRun]
    skipped: bool = False
    skip_reason: str | None = None


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def _openrouter_headers() -> dict[str, str]:
    headers: dict[str, str] = {}
    if settings.openrouter_api_key and settings.openrouter_api_key.strip():
        headers["Authorization"] = f"Bearer {settings.openrouter_api_key}"
    return headers


def _provider_from_model(model: dict[str, Any]) -> str:
    model_id = model.get("id", "")
    if "/" in model_id:
        return model_id.split("/", 1)[0]
    return model_id


def _prompt_price_per_million(pricing: dict[str, Any] | None) -> float | None:
    if not pricing:
        return None
    raw = pricing.get("prompt")
    if raw is None:
        return None
    try:
        return float(raw) * 1_000_000
    except (TypeError, ValueError):
        return None


def _pricing_tier(model: dict[str, Any]) -> str:
    model_id = model.get("id", "")
    if model_id.endswith(":free"):
        return "free"
    pricing = model.get("pricing") or {}
    try:
        prompt = float(pricing.get("prompt", "0") or "0")
        completion = float(pricing.get("completion", "0") or "0")
    except (TypeError, ValueError):
        return "paid"
    if prompt == 0.0 and completion == 0.0:
        return "free"
    return "paid"


def _extract_reported_throughput(model: dict[str, Any]) -> float | None:
    """Read throughput from known OpenRouter model-schema locations."""
    for key in ("throughput", "throughput_p50", "p50_throughput"):
        if key not in model:
            continue
        value = model.get(key)
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    for container_key in ("stats", "routing", "performance"):
        container = model.get(container_key)
        if not isinstance(container, dict):
            continue
        for key in ("throughput", "throughput_p50", "p50_throughput", "throughput_last_30m"):
            if key not in container:
                continue
            value = container.get(key)
            if value is None:
                return None
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

    top_provider = model.get("top_provider")
    if isinstance(top_provider, dict):
        for key in ("throughput", "throughput_p50", "throughput_last_30m"):
            if key not in top_provider:
                continue
            value = top_provider.get(key)
            if value is None:
                return None
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

    return None


def _model_explicitly_lacks_throughput(model: dict[str, Any]) -> bool:
    """True when the API exposes a throughput field that is explicitly null."""
    if "throughput" in model and model.get("throughput") is None:
        return True
    for container_key in ("stats", "routing", "performance"):
        container = model.get(container_key)
        if isinstance(container, dict) and "throughput" in container:
            return container.get("throughput") is None
    return False


def _is_chat_completion_model(model: dict[str, Any]) -> bool:
    """Keep plain text chat/completion models; drop embeddings/image/audio-only."""
    architecture = model.get("architecture") or {}
    input_modalities = architecture.get("input_modalities") or []
    output_modalities = architecture.get("output_modalities") or []
    supported_parameters = model.get("supported_parameters") or []
    modality = str(architecture.get("modality", "")).lower()

    if "text" not in input_modalities:
        return False
    if output_modalities != ["text"]:
        return False
    if "max_tokens" not in supported_parameters:
        return False
    if "embed" in modality:
        return False
    return True


def _throughput_tail_start_index(models: list[dict[str, Any]]) -> int | None:
    """Return the first index in a throughput-sorted list with no throughput score."""
    for index, model in enumerate(models):
        if _model_explicitly_lacks_throughput(model):
            return index
    return None


def fetch_sorted_models() -> list[dict[str, Any]]:
    with httpx.Client(timeout=MODELS_API_TIMEOUT_SECONDS, trust_env=False) as client:
        response = client.get(OPENROUTER_MODELS_URL, headers=_openrouter_headers())
        response.raise_for_status()
        payload = response.json()
    return payload.get("data", [])


def discover_models(*, max_models: int = MAX_MODELS) -> tuple[list[DiscoveredModel], str]:
    """Resolve the fastest text-chat models from OpenRouter's live catalog."""
    resolved_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sorted_models = fetch_sorted_models()
    tail_start = _throughput_tail_start_index(sorted_models)
    eligible_slice = sorted_models if tail_start is None else sorted_models[:tail_start]

    discovered: list[DiscoveredModel] = []
    for sort_rank, model in enumerate(eligible_slice, start=1):
        model_id = model.get("id", "")
        if not model_id:
            continue

        if not _is_chat_completion_model(model):
            continue
        if _model_explicitly_lacks_throughput(model):
            break

        price = _prompt_price_per_million(model.get("pricing"))
        if not (
            model_id.endswith(":free")
            or model_id
            in ["google/gemini-2.5-flash-lite", "deepseek/deepseek-v4-flash"]
            or (price is not None and price <= 0.20)
        ):
            continue

        discovered.append(
            DiscoveredModel(
                slug=model_id,
                provider=_provider_from_model(model),
                pricing_tier=_pricing_tier(model),
                prompt_price_per_million=price,
                reported_throughput=_extract_reported_throughput(model),
                sort_rank=sort_rank,
            )
        )
        if len(discovered) >= max_models:
            break

    if not discovered:
        raise SystemExit(
            "No eligible throughput-ranked chat models found on OpenRouter."
        )

    return discovered, resolved_at


def log_discovered_models(
    models: list[DiscoveredModel], resolved_at: str, *, max_models: int
) -> None:
    print(f"Resolved {len(models)} models at {resolved_at} (target {max_models})")
    print(
        f"{'Rank':>4}  {'Slug':<44} {'Provider':<16} {'Tier':<5} "
        f"{'$/M prompt':>10}  {'Throughput':>12}"
    )
    print("-" * 100)
    for model in models:
        price = (
            f"{model.prompt_price_per_million:.4f}"
            if model.prompt_price_per_million is not None
            else "N/A"
        )
        throughput = (
            f"{model.reported_throughput:.1f}"
            if model.reported_throughput is not None
            else "sort-only"
        )
        print(
            f"{model.sort_rank:>4}  {model.slug:<44} {model.provider:<16} "
            f"{model.pricing_tier:<5} {price:>10}  {throughput:>12}"
        )


def build_benchmark_messages() -> list[dict[str, str]]:
    """Assemble production-equivalent SOAP prompt payload (RAG skipped via mock)."""
    summary = MedicalSummary(
        chief_complaint="Chest pain",
        symptoms=["chest pain", "shortness of breath"],
        symptom_duration="2 days",
        symptom_severity="moderate",
        additional_notes=(
            "Substernal chest pain for 2 days, moderate severity, radiating to left arm"
        ),
        is_hpi_complete=True,
    )

    pmh_answers = [
        PMHAnswer(
            category_id="cat_cardio",
            is_selected=True,
            question_responses={
                "pmh_cardio_cad_001": True,
                "pmh_cardio_cad_001_date": PMH_DATE_VALUE,
            },
        ),
    ]
    pmh_context = format_pmh_for_prompt(pmh_answers)

    chat_history = [
        {
            "role": "user",
            "content": "I have been having chest pain for the past two days.",
        },
        {
            "role": "assistant",
            "content": "Can you describe the pain? Is it sharp, dull, or pressure-like?",
        },
        {
            "role": "user",
            "content": "It feels like pressure in the center of my chest.",
        },
        {
            "role": "assistant",
            "content": "Does the pain radiate anywhere, such as your arm or jaw?",
        },
    ]

    generator = SOAPNoteGenerator(rag_service=MagicMock())
    context = generator._build_context(
        summary,
        chat_history=chat_history,
        pmh_context=pmh_context,
    )

    return [
        {"role": "system", "content": generator._get_system_prompt()},
        {"role": "user", "content": context},
    ]


async def benchmark_single_completion(
    client: AsyncOpenAI,
    *,
    model_slug: str,
    messages: list[dict[str, str]],
    timeout_seconds: float,
    temperature: float,
    max_tokens: int,
    retry_count: int,
) -> CompletionRun:
    attempts = retry_count + 1

    for attempt in range(1, attempts + 1):
        start = time.perf_counter()
        try:
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=model_slug,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=False,
                ),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            if attempt < attempts:
                continue
            return CompletionRun(
                status="timeout",
                ttft_ms=None,
                tps=None,
                error=f"Exceeded {timeout_seconds}s timeout",
            )
        except Exception as exc:
            if attempt < attempts:
                continue
            return CompletionRun(
                status="error",
                ttft_ms=None,
                tps=None,
                error=str(exc),
            )

        total_ms = (time.perf_counter() - start) * 1000
        # Non-streaming workload: TTFT is approximated as total response latency
        # because the first token is not observable until the full response arrives.
        ttft_ms = total_ms

        completion_tokens: int | None = None
        usage = getattr(response, "usage", None)
        if usage is not None:
            completion_tokens = getattr(usage, "completion_tokens", None)

        output = ""
        if response.choices:
            message = response.choices[0].message
            output = message.content or ""

        tps: float | None = None
        if completion_tokens and completion_tokens > 0 and total_ms > 0:
            tps = completion_tokens / (total_ms / 1000)
        elif output and total_ms > 0:
            estimated_tokens = max(len(output) / 4, 1)
            tps = estimated_tokens / (total_ms / 1000)

        return CompletionRun(
            status="success",
            ttft_ms=round(ttft_ms, 1),
            tps=round(tps, 1) if tps is not None else None,
        )

    return CompletionRun(
        status="error",
        ttft_ms=None,
        tps=None,
        error="Exhausted retries",
    )


async def benchmark_model(
    client: AsyncOpenAI,
    *,
    model: DiscoveredModel,
    messages: list[dict[str, str]],
    runs_per_model: int,
    timeout_seconds: float,
    temperature: float,
    max_tokens: int,
    retry_count: int,
    semaphore: asyncio.Semaphore,
) -> ModelBenchmarkResult:
    async with semaphore:
        runs: list[CompletionRun] = []
        print(f"\n--- {model.slug} ---")

        for run_index in range(1, runs_per_model + 1):
            try:
                result = await benchmark_single_completion(
                    client,
                    model_slug=model.slug,
                    messages=messages,
                    timeout_seconds=timeout_seconds,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    retry_count=retry_count,
                )
            except Exception as exc:
                result = CompletionRun(
                    status="error",
                    ttft_ms=None,
                    tps=None,
                    error=str(exc),
                )

            runs.append(result)
            ttft = (
                f"{result.ttft_ms:.0f}ms"
                if result.ttft_ms is not None
                else "N/A"
            )
            tps = f"{result.tps:.1f}" if result.tps is not None else "N/A"
            print(
                f"  run {run_index}: status={result.status} ttft={ttft} tps={tps}"
            )
            if result.error:
                print(f"           error: {result.error}")

        ttft_values = [run.ttft_ms for run in runs if run.ttft_ms is not None]
        tps_values = [run.tps for run in runs if run.tps is not None]
        error_count = sum(1 for run in runs if run.status != "success")

        return ModelBenchmarkResult(
            model=model,
            median_ttft_ms=_median(ttft_values),
            median_tps=_median(tps_values),
            error_count=error_count,
            runs=runs,
        )


def _chunked(items: list[DiscoveredModel], size: int) -> list[list[DiscoveredModel]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


async def run_benchmarks(
    models: list[DiscoveredModel],
    *,
    resolved_at: str,
    runs_per_model: int,
    timeout_seconds: float,
    temperature: float,
    max_tokens: int,
    max_concurrent_requests: int,
    batch_delay_seconds: float,
    retry_count: int,
) -> list[ModelBenchmarkResult]:
    api_key = settings.openrouter_api_key
    if not api_key or not api_key.strip():
        raise SystemExit(
            "OPENROUTER_API_KEY is not configured. Set it in backend/.env before running."
        )

    client = AsyncOpenAI(
        base_url=settings.openrouter_base_url,
        api_key=api_key,
        max_retries=0,
        http_client=httpx.AsyncClient(timeout=timeout_seconds + HTTP_CLIENT_BUFFER_SECONDS),
        default_headers={
            "HTTP-Referer": settings.openrouter_http_referer,
            "X-Title": settings.openrouter_app_title,
        },
    )

    messages = build_benchmark_messages()
    semaphore = asyncio.Semaphore(max_concurrent_requests)
    all_results: list[ModelBenchmarkResult] = []

    print(
        f"\nBenchmarking {len(models)} models, {runs_per_model} non-streaming runs each"
    )
    print(
        f"Concurrency={max_concurrent_requests} | timeout={timeout_seconds}s | "
        f"batch_delay={batch_delay_seconds}s | max_tokens={max_tokens}"
    )
    print(f"Payload chars: {len(messages[1]['content'])}")

    try:
        for batch_index, batch in enumerate(
            _chunked(models, max_concurrent_requests), start=1
        ):
            print(f"\nBatch {batch_index} ({len(batch)} models)")
            gathered = await asyncio.gather(
                *[
                    benchmark_model(
                        client,
                        model=model,
                        messages=messages,
                        runs_per_model=runs_per_model,
                        timeout_seconds=timeout_seconds,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        retry_count=retry_count,
                        semaphore=semaphore,
                    )
                    for model in batch
                ],
                return_exceptions=True,
            )

            for model, outcome in zip(batch, gathered, strict=True):
                if isinstance(outcome, Exception):
                    print(f"Skipping {model.slug}: {outcome}")
                    all_results.append(
                        ModelBenchmarkResult(
                            model=model,
                            median_ttft_ms=None,
                            median_tps=None,
                            error_count=runs_per_model,
                            runs=[],
                            skipped=True,
                            skip_reason=str(outcome),
                        )
                    )
                    continue
                all_results.append(outcome)

            if batch_index < len(_chunked(models, max_concurrent_requests)):
                await asyncio.sleep(batch_delay_seconds)
    finally:
        await client.close()

    return all_results


def _csv_output_path(resolved_at: str) -> Path:
    date_part = resolved_at.split("T", 1)[0].replace("-", "")
    if "T" in resolved_at:
        time_part = resolved_at.split("T", 1)[1].replace(":", "")
        stamp = f"{date_part}_{time_part}"
    else:
        stamp = date_part
    return RESULTS_DIR / f"latency_{stamp}.csv"


def write_results_csv(
    *,
    discovered: list[DiscoveredModel],
    results: list[ModelBenchmarkResult],
    resolved_at: str,
    max_models_requested: int,
) -> Path:
    output_path = _csv_output_path(resolved_at)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)

        writer.writerow(["# discovery_metadata"])
        writer.writerow(["resolved_date", resolved_at])
        writer.writerow(["max_models_requested", max_models_requested])
        writer.writerow(["models_discovered", len(discovered)])
        writer.writerow(["models_benchmarked", len(results)])
        writer.writerow([])

        writer.writerow(["# resolved_model_list"])
        writer.writerow(
            [
                "sort_rank",
                "model_slug",
                "provider",
                "pricing_tier",
                "prompt_price_per_million",
                "reported_throughput",
                "resolved_date",
            ]
        )
        for model in discovered:
            writer.writerow(
                [
                    model.sort_rank,
                    model.slug,
                    model.provider,
                    model.pricing_tier,
                    "" if model.prompt_price_per_million is None else model.prompt_price_per_million,
                    "" if model.reported_throughput is None else model.reported_throughput,
                    resolved_at,
                ]
            )
        writer.writerow([])

        writer.writerow(["# benchmark_results"])
        writer.writerow(
            [
                "model_slug",
                "provider",
                "pricing_tier",
                "prompt_price_per_million",
                "reported_throughput",
                "median_ttft_ms",
                "median_tps",
                "error_count",
                "resolved_date",
            ]
        )
        for result in results:
            model = result.model
            writer.writerow(
                [
                    model.slug,
                    model.provider,
                    model.pricing_tier,
                    "" if model.prompt_price_per_million is None else model.prompt_price_per_million,
                    "" if model.reported_throughput is None else model.reported_throughput,
                    "" if result.median_ttft_ms is None else round(result.median_ttft_ms, 1),
                    "" if result.median_tps is None else round(result.median_tps, 1),
                    result.error_count,
                    resolved_at,
                ]
            )

    return output_path


def print_summary(
    results: list[ModelBenchmarkResult],
    *,
    max_models_requested: int,
) -> None:
    successful = [result for result in results if not result.skipped]
    print("\n" + "=" * 88)
    print("Latency benchmark summary (median of non-streaming runs)")
    print("=" * 88)
    header = (
        f"{'Model':<42} {'Tier':<5} {'Med TTFT':>10} {'Med TPS':>9} {'Errors':>8}"
    )
    print(header)
    print("-" * len(header))

    for result in sorted(
        successful,
        key=lambda item: (
            item.median_ttft_ms if item.median_ttft_ms is not None else float("inf")
        ),
    ):
        ttft = (
            f"{result.median_ttft_ms:.0f}ms"
            if result.median_ttft_ms is not None
            else "N/A"
        )
        tps = f"{result.median_tps:.1f}" if result.median_tps is not None else "N/A"
        print(
            f"{result.model.slug:<42} {result.model.pricing_tier:<5} "
            f"{ttft:>10} {tps:>9} {result.error_count:>8}"
        )

    print("=" * len(header))
    if len(successful) < max_models_requested:
        print(
            f"\nNote: {len(successful)} of {max_models_requested} requested models "
            "returned benchmark results (failures are not backfilled)."
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Discover the fastest OpenRouter chat models by throughput and "
            "benchmark SOAP generation latency."
        )
    )
    parser.add_argument("--max-models", type=int, default=MAX_MODELS)
    parser.add_argument("--runs", type=int, default=RUNS_PER_MODEL)
    parser.add_argument("--timeout", type=float, default=COMPLETION_TIMEOUT_SECONDS)
    parser.add_argument("--concurrency", type=int, default=MAX_CONCURRENT_REQUESTS)
    parser.add_argument("--batch-delay", type=float, default=BATCH_DELAY_SECONDS)
    parser.add_argument("--retries", type=int, default=RETRY_COUNT)
    parser.add_argument("--temperature", type=float, default=TEMPERATURE)
    parser.add_argument("--max-tokens", type=int, default=MAX_COMPLETION_TOKENS)
    return parser.parse_args()


async def async_main() -> None:
    args = parse_args()

    discovered, resolved_at = discover_models(max_models=args.max_models)
    log_discovered_models(discovered, resolved_at, max_models=args.max_models)

    results = await run_benchmarks(
        discovered,
        resolved_at=resolved_at,
        runs_per_model=args.runs,
        timeout_seconds=args.timeout,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        max_concurrent_requests=args.concurrency,
        batch_delay_seconds=args.batch_delay,
        retry_count=args.retries,
    )

    csv_path = write_results_csv(
        discovered=discovered,
        results=results,
        resolved_at=resolved_at,
        max_models_requested=args.max_models,
    )
    print_summary(results, max_models_requested=args.max_models)
    print(f"\nResults saved to {csv_path}")


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
