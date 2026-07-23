import json
from io import BytesIO
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.main import app as fastapi_app
from app.models.audit_log import AuditLog
from app.models.medical_knowledge import MedicalKnowledge
from app.services.embedding_service import EmbeddingServiceError
from app.services.kb_ingest_service import (
    KbIngestValidationError,
    ingest_documents,
    parse_json_payload,
    validate_document,
)
from tests.test_admin import _register_and_login
from tests.test_api_integration import _auth_headers


def _valid_doc(**overrides) -> dict:
    base = {
        "document_id": "guideline-test-htn",
        "title": "Hypertension Guideline Excerpt",
        "source": "ACC/AHA Test Source",
        "published_at": "2023-06-15",
        "content": "Hypertension is defined as systolic blood pressure of 130 mmHg or higher.",
    }
    base.update(overrides)
    return base


class TestKbIngestValidation:
    def test_requires_title_source_and_published_at(self):
        with pytest.raises(KbIngestValidationError, match="title"):
            validate_document(
                {
                    "document_id": "x",
                    "source": "S",
                    "published_at": "2024-01-01",
                    "content": "body",
                }
            )

        with pytest.raises(KbIngestValidationError, match="source"):
            validate_document(
                {
                    "document_id": "x",
                    "title": "T",
                    "published_at": "2024-01-01",
                    "content": "body",
                }
            )

        with pytest.raises(KbIngestValidationError, match="published_at"):
            validate_document(
                {
                    "document_id": "x",
                    "title": "T",
                    "source": "S",
                    "content": "body",
                }
            )

    def test_parse_json_documents_wrapper(self):
        raw = json.dumps({"documents": [_valid_doc()]}).encode()
        docs = parse_json_payload(raw)
        assert len(docs) == 1
        assert docs[0]["title"] == "Hypertension Guideline Excerpt"
        assert docs[0]["metadata"]["published_at"] == "2023-06-15"


@pytest.mark.asyncio
async def test_ingest_documents_persists_chunks(db, test_db_engine):
    fake_embedding = [0.01] * 768

    with patch(
        "app.services.kb_ingest_service.embedding_service.generate_embedding",
        new=AsyncMock(return_value=fake_embedding),
    ):
        results = await ingest_documents(db, [_valid_doc()], commit=True)

    assert len(results) == 1
    assert results[0].chunks_inserted >= 1

    rows = (
        await db.execute(
            select(MedicalKnowledge).where(
                MedicalKnowledge.document_id == "guideline-test-htn"
            )
        )
    ).scalars().all()
    assert len(rows) == results[0].chunks_inserted
    assert rows[0].source == "ACC/AHA Test Source"
    assert rows[0].document_metadata["title"] == "Hypertension Guideline Excerpt"


@pytest.mark.asyncio
async def test_ingest_documents_surfaces_embedding_failure(db, test_db_engine):
    with patch(
        "app.services.kb_ingest_service.embedding_service.generate_embedding",
        new=AsyncMock(side_effect=EmbeddingServiceError("Ollama unavailable")),
    ):
        with pytest.raises(EmbeddingServiceError, match="Ollama unavailable"):
            await ingest_documents(db, [_valid_doc()], commit=True)


@pytest.mark.asyncio
async def test_admin_kb_ingest_endpoint(db, test_db_engine):
    fake_embedding = [0.02] * 768
    transport = ASGITransport(app=fastapi_app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        admin_token = await _register_and_login(
            client, role="admin", seed="AdminKbIngest"
        )
        patient_token = await _register_and_login(
            client, role="patient", seed="PatientKbIngest"
        )

        payload = json.dumps({"documents": [_valid_doc()]}).encode()

        with patch(
            "app.services.kb_ingest_service.embedding_service.generate_embedding",
            new=AsyncMock(return_value=fake_embedding),
        ):
            ok = await client.post(
                "/api/admin/kb/ingest",
                headers=_auth_headers(admin_token),
                files={"file": ("kb.json", BytesIO(payload), "application/json")},
            )
        assert ok.status_code == 200, ok.text
        body = ok.json()
        assert body["status"] == "ok"
        assert body["documents_processed"] == 1
        assert body["chunks_inserted"] >= 1
        assert body["documents"][0]["document_id"] == "guideline-test-htn"

        audits = (
            await db.execute(
                select(AuditLog).where(AuditLog.action == "kb_document_ingested")
            )
        ).scalars().all()
        assert len(audits) >= 1
        assert audits[0].resource_type == "medical_knowledge"
        assert audits[0].resource_id == "guideline-test-htn"

        forbidden = await client.post(
            "/api/admin/kb/ingest",
            headers=_auth_headers(patient_token),
            files={"file": ("kb.json", BytesIO(payload), "application/json")},
        )
        assert forbidden.status_code == 403

        missing_fields = json.dumps(
            {
                "documents": [
                    {
                        "document_id": "bad",
                        "content": "text only",
                    }
                ]
            }
        ).encode()
        bad = await client.post(
            "/api/admin/kb/ingest",
            headers=_auth_headers(admin_token),
            files={"file": ("bad.json", BytesIO(missing_fields), "application/json")},
        )
        assert bad.status_code == 400
        detail = bad.json()["detail"].lower()
        assert "published_at" in detail or "title" in detail or "missing" in detail

        with patch(
            "app.services.kb_ingest_service.embedding_service.generate_embedding",
            new=AsyncMock(side_effect=EmbeddingServiceError("embedding provider down")),
        ):
            failed = await client.post(
                "/api/admin/kb/ingest",
                headers=_auth_headers(admin_token),
                files={"file": ("kb.json", BytesIO(payload), "application/json")},
            )
        assert failed.status_code == 503
        assert "embedding" in failed.json()["detail"].lower() or "provider" in failed.json()["detail"].lower() or "Ollama" in failed.json()["detail"] or "down" in failed.json()["detail"].lower()
