"""Correlation ID HTTP propagation and soap_task rebind."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.observability.context import clear, get_correlation_id
from app.core.observability.middleware import CORRELATION_HEADER
from app.main import app


@pytest.fixture(autouse=True)
def _clear_ctx():
    clear()
    yield
    clear()


@pytest.mark.asyncio
async def test_metrics_endpoint_exposes_prometheus_text() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "previsit_soap_success_total" in response.text


@pytest.mark.asyncio
async def test_request_id_generated_and_echoed() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert CORRELATION_HEADER in response.headers
    assert len(response.headers[CORRELATION_HEADER]) > 0


@pytest.mark.asyncio
async def test_request_id_accepted_from_client() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/health",
            headers={CORRELATION_HEADER: "client-corr-123"},
        )
    assert response.headers[CORRELATION_HEADER] == "client-corr-123"


@pytest.mark.asyncio
async def test_run_soap_generation_rebinds_correlation_id() -> None:
    from app.services import soap_task

    captured: dict = {}

    async def fake_build(db, session_id):
        captured["correlation_id"] = get_correlation_id()
        raise ValueError("No clinical summary available for ClinicalContext")

    session = MagicMock()
    session.patient_id = 7
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

    async def execute_side_effect(stmt):
        sql = str(stmt)
        if "summaries" in sql.lower() or "Summary" in sql:
            return summary_result
        return session_result

    db.execute = AsyncMock(side_effect=execute_side_effect)
    db.commit = AsyncMock()

    with patch.object(soap_task, "get_async_session", return_value=db_cm):
        with patch.object(
            soap_task.clinical_context_builder,
            "build",
            side_effect=fake_build,
        ):
            await soap_task.run_soap_generation(
                session_id=99,
                correlation_id="propagated-corr-id",
                entry="retry",
            )

    assert captured["correlation_id"] == "propagated-corr-id"
    assert session.soap_status == "failed"
