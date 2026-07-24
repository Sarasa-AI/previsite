"""ClinicalPipelineEvent / AITelemetryEvent contract tests."""

from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.core.observability.context import bind, clear
from app.core.observability.telemetry import (
    AITelemetryEvent,
    ClinicalPipelineEvent,
    build_ai_telemetry_event,
    build_pipeline_event,
    emit_ai_telemetry,
    emit_pipeline_event,
)


def setup_function() -> None:
    clear()
    bind(correlation_id="corr-test-1", session_id=10, patient_id=20)


def teardown_function() -> None:
    clear()


def test_clinical_pipeline_event_serializes() -> None:
    event = build_pipeline_event(
        module="clinical_context",
        pipeline_stage="clinical_context.build",
        latency_ms=48,
        status="success",
        lab_count=2,
        medication_count=1,
        pmh_count=4,
    )
    assert isinstance(event, ClinicalPipelineEvent)
    data = event.model_dump()
    assert data["event"] == "clinical_pipeline"
    assert data["correlation_id"] == "corr-test-1"
    assert data["request_id"] == "corr-test-1"
    assert data["module"] == "clinical_context"
    assert "soap_note" not in data


def test_ai_telemetry_inherits_and_extends() -> None:
    event = build_ai_telemetry_event(
        module="soap",
        pipeline_stage="soap.generate",
        latency_ms=3000,
        status="success",
        llm_model="openai/gpt-4o-mini",
        prompt_version="soap_v1",
        completion_version="soap_generator.v1",
        input_tokens=100,
        output_tokens=50,
        evidence_count=3,
    )
    assert isinstance(event, AITelemetryEvent)
    assert isinstance(event, ClinicalPipelineEvent)
    data = event.model_dump()
    assert data["event"] == "ai_telemetry"
    assert data["llm_model"] == "openai/gpt-4o-mini"
    assert data["input_tokens"] == 100
    assert data["module"] == "soap"


def test_phi_fields_rejected_on_model() -> None:
    with pytest.raises(ValidationError):
        ClinicalPipelineEvent(
            correlation_id="x",
            request_id="x",
            module="soap",
            pipeline_stage="soap.generate",
            latency_ms=1,
            status="success",
            soap_note="Patient has chest pain",  # type: ignore[call-arg]
        )


def test_emit_pipeline_event_writes_structured_log() -> None:
    event = build_pipeline_event(
        module="ocr",
        pipeline_stage="ocr.extract",
        latency_ms=12,
        status="success",
    )
    with patch("app.core.observability.telemetry.logger") as mock_logger:
        emit_pipeline_event(event)
        mock_logger.bind.assert_called_once()
        kwargs = mock_logger.bind.call_args.kwargs
        assert kwargs["event"] == "clinical_pipeline"
        assert "soap_note" not in kwargs
        mock_logger.bind.return_value.log.assert_called_once()


def test_emit_ai_telemetry_records_tokens_and_cost() -> None:
    event = build_ai_telemetry_event(
        module="soap",
        pipeline_stage="soap.generate",
        latency_ms=100,
        status="success",
        llm_model="openai/gpt-4o-mini",
        input_tokens=1000,
        output_tokens=200,
    )
    with patch("app.core.observability.telemetry.logger") as mock_logger:
        with patch("app.core.observability.telemetry.observe_tokens") as mock_tokens:
            with patch("app.core.observability.telemetry.observe_cost") as mock_cost:
                emit_ai_telemetry(event)
                mock_tokens.assert_called_once()
                mock_cost.assert_called_once()
                kwargs = mock_logger.bind.call_args.kwargs
                assert kwargs["event"] == "ai_telemetry"
                assert kwargs.get("estimated_cost_usd") is not None
