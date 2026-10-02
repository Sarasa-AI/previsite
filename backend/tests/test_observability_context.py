"""Observability context bind/clear and nested stage fields."""

from app.core.observability.context import (
    bind,
    clear,
    get_context,
    get_correlation_id,
    new_correlation_id,
)


def setup_function() -> None:
    clear()


def teardown_function() -> None:
    clear()


def test_bind_and_clear_correlation() -> None:
    cid = new_correlation_id()
    bind(correlation_id=cid, session_id=42, patient_id=7, module="soap")
    ctx = get_context()
    assert get_correlation_id() == cid
    assert ctx.session_id == 42
    assert ctx.patient_id == 7
    assert ctx.module == "soap"
    assert ctx.request_id == cid
    clear()
    assert get_correlation_id() is None
    assert get_context().session_id is None


def test_nested_stage_context_updates() -> None:
    bind(correlation_id="abc", module="soap")
    bind(pipeline_stage="soap.generate")
    assert get_context().pipeline_stage == "soap.generate"
    bind(pipeline_stage="rag.retrieve", module="rag")
    ctx = get_context()
    assert ctx.pipeline_stage == "rag.retrieve"
    assert ctx.module == "rag"
    assert ctx.correlation_id == "abc"


def test_as_log_extra_omits_empty() -> None:
    bind(correlation_id="cid-1")
    extra = get_context().as_log_extra()
    assert extra["correlation_id"] == "cid-1"
    assert extra["request_id"] == "cid-1"
    assert "session_id" not in extra
