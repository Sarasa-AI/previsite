"""Failure observability: recoverable RAG, builder errors, SOAP failures."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.observability.context import bind, clear
from app.core.observability.metrics import reset_metrics_for_tests
from app.schemas.clinical_context import ClinicalContext
from app.schemas.medical import MedicalSummary
from app.services.soap_generator import SOAPNoteGenerator


def setup_function() -> None:
    clear()
    reset_metrics_for_tests()
    bind(correlation_id="fail-corr", session_id=1, patient_id=1)


def teardown_function() -> None:
    clear()


def _clinical_context() -> ClinicalContext:
    return ClinicalContext(
        session_id=1,
        patient_id=1,
        summary=MedicalSummary(
            chief_complaint="Chest pain",
            additional_notes="substernal pain",
        ),
    )


@pytest.mark.asyncio
async def test_rag_soft_fail_emits_recoverable_and_continues() -> None:
    gen = SOAPNoteGenerator.__new__(SOAPNoteGenerator)
    gen.rag_service = MagicMock()
    gen.rag_service.search_similar_knowledge = AsyncMock(
        side_effect=RuntimeError("vector store down")
    )
    gen.openrouter_client = MagicMock()

    usage = MagicMock()
    usage.prompt_tokens = 10
    usage.completion_tokens = 5
    completion = MagicMock()
    completion.choices = [MagicMock(message=MagicMock(content="S: ok\nO: ok\nA: ok\nP: ok"))]
    completion.usage = usage
    gen.openrouter_client.chat.completions.create = AsyncMock(return_value=completion)

    with patch(
        "app.core.observability.timing.emit_pipeline_failure"
    ) as mock_stage_fail:
        with patch.object(gen, "_apply_citation_verification", new=AsyncMock()) as mock_verify:
            mock_verify.return_value = MagicMock(
                content="S: ok\nO: ok\nA: ok\nP: ok",
                citations=[],
                verification_status="unverified",
            )
            with patch(
                "app.services.soap_generator.validate_and_format_conflicts",
                return_value=("S: ok\nO: ok\nA: ok\nP: ok", []),
            ):
                with patch("app.services.soap_generator.emit_ai_telemetry"):
                    with patch.object(
                        gen,
                        "_get_system_prompt",
                        return_value="system",
                    ):
                        with patch.object(
                            gen,
                            "_extract_patient_hpi",
                            return_value="chest pain",
                        ):
                            with patch.object(gen, "_build_citations", return_value=[]):
                                with patch.object(
                                    gen, "_format_pmh_assertion_registry", return_value=""
                                ):
                                    with patch.object(
                                        gen, "_build_context", return_value="ctx"
                                    ):
                                        with patch.object(
                                            gen,
                                            "_format_medical_evidence",
                                            return_value="",
                                        ):
                                            result = await gen.generate_soap_note(
                                                _clinical_context(), db=AsyncMock()
                                            )

    assert result["status"] == "success"
    assert mock_stage_fail.called
    kwargs = mock_stage_fail.call_args.kwargs
    assert kwargs["recoverable"] is True
    assert kwargs["stage"] == "rag.retrieve"


@pytest.mark.asyncio
async def test_builder_value_error_emits_structured_failure() -> None:
    from app.services import soap_task

    session = MagicMock()
    session.patient_id = 3
    session.soap_status = "pending"
    session.soap_error_detail = None

    db_cm = MagicMock()
    db = AsyncMock()
    db_cm.__aenter__ = AsyncMock(return_value=db)
    db_cm.__aexit__ = AsyncMock(return_value=None)

    session_result = MagicMock()
    session_result.scalar_one_or_none.return_value = session
    summary_result = MagicMock()
    summary_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(side_effect=[session_result, summary_result])
    db.commit = AsyncMock()

    with patch.object(soap_task, "get_async_session", return_value=db_cm):
        with patch.object(
            soap_task.clinical_context_builder,
            "build",
            AsyncMock(side_effect=ValueError("No clinical summary available")),
        ):
            with patch(
                "app.core.observability.timing.emit_pipeline_failure"
            ) as mock_fail:
                await soap_task.run_soap_generation(session_id=5, correlation_id="c1")

    assert session.soap_status == "failed"
    assert mock_fail.called
    assert mock_fail.call_args.kwargs["recoverable"] is False


@pytest.mark.asyncio
async def test_soap_exception_path_emits_ai_failure_telemetry() -> None:
    gen = SOAPNoteGenerator.__new__(SOAPNoteGenerator)
    gen.rag_service = MagicMock()
    gen.rag_service.search_similar_knowledge = AsyncMock(return_value=[])
    gen.openrouter_client = None

    with patch("app.services.soap_generator.emit_ai_telemetry") as mock_ai:
        result = await gen.generate_soap_note(_clinical_context(), db=AsyncMock())

    assert result["status"] == "error"
    assert mock_ai.called
    event = mock_ai.call_args.args[0]
    assert event.status == "failure"
    assert event.error_type == "ValueError"
    assert event.event == "ai_telemetry"
