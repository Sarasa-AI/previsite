"""Metrics recording and Prometheus exposition."""

from app.core.observability.metrics import (
    inc_soap_failure,
    inc_soap_success,
    metrics_response,
    observe_cost,
    observe_duration,
    observe_ocr_duration,
    observe_tokens,
    reset_metrics_for_tests,
)


def setup_function() -> None:
    reset_metrics_for_tests()


def test_duration_and_success_failure_recorded() -> None:
    observe_duration("soap.generate", 1200, "success")
    observe_duration("clinical_context.build", 40, "success")
    observe_ocr_duration(80, "success", "lab")
    observe_duration("summary.build", 500, "success")
    observe_duration("rag.retrieve", 100, "failure")
    inc_soap_success()
    inc_soap_failure("ValueError")
    observe_tokens("openai/gpt-4o-mini", 100, 50)
    observe_cost("openai/gpt-4o-mini", 0.001)

    body, content_type = metrics_response()
    text = body.decode("utf-8")
    assert "text/plain" in content_type
    assert "previsit_soap_generation_duration_seconds" in text
    assert "previsit_clinical_context_build_duration_seconds" in text
    assert "previsit_ocr_duration_seconds" in text
    assert "previsit_summary_duration_seconds" in text
    assert "previsit_rag_duration_seconds" in text
    assert "previsit_pipeline_stage_duration_seconds" in text
    assert "previsit_soap_success_total" in text
    assert "previsit_soap_failure_total" in text
    assert "previsit_llm_tokens_total" in text
    assert "previsit_llm_estimated_cost_usd_total" in text
    assert 'error_type="ValueError"' in text
