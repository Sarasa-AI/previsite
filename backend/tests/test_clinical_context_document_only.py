"""Regression: a document-only session must keep its evidence visible.

A session whose only clinical content is an uploaded document — no intake
clinical summary and no chat summary — used to raise inside
``ClinicalContextBuilder.build()`` *before* document evidence was projected.
The workspace and clinical-content endpoints map that ``ValueError`` to
``404 WORKSPACE_SESSION_NOT_FOUND``, so extracted labs sat in the database
while the doctor was told the session did not exist.

These tests pin both halves of the repair:

* evidence-backed but summary-less sessions build a minimal context and keep
  their labs, and
* a genuinely empty session still fails closed.

The extraction payload here is produced by the real production extractor over a
transcription shaped exactly like the PDF text-layer engine emits, so the test
exercises the deterministic ``extraction -> ClinicalContext`` contract instead
of asserting against a hand-written payload that could drift from it.
"""

from __future__ import annotations

import json

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ArtifactKind, ArtifactStatus, DocumentArtifact
from app.models import File as FileModel
from app.services.clinical_context_builder import ClinicalContextBuilder
from app.services.document_extraction import extract_clinical_values
from app.services.document_ocr import (
    ENGINE_PDF_TEXT_LAYER,
    OcrDocument,
    OcrLine,
    OcrPage,
    OcrWord,
)
from tests.test_soap_clinical_context import _register_patient_async

#: The deterministic verification document. Values are asserted verbatim.
DOCUMENT_LINES = (
    "Patient ID: PV-TEST-84721",
    "Date: 2026-08-20",
    "Hemoglobin: 13.7 g/dL",
    "WBC: 8,421 /uL",
    "Platelets: 245,000 /uL",
)


def _text_layer_document(lines: tuple[str, ...]) -> OcrDocument:
    """Build an OcrDocument shaped like the PDF text-layer engine's output.

    A text layer reports no per-word confidence, which is why this path is not
    flagged ``needs_review`` — absence of a confidence score is not low
    confidence (see ``OcrDocument.needs_review``).
    """
    ocr_lines = tuple(
        OcrLine(
            page=1,
            text=line,
            words=(OcrWord(text=line, confidence=None, page=1, bbox=None),),
        )
        for line in lines
    )
    return OcrDocument(
        engine=ENGINE_PDF_TEXT_LAYER,
        engine_version="pypdf",
        pages=(OcrPage(page_number=1, text="\n".join(lines), lines=ocr_lines),),
    )


async def _create_bare_session(
    client: AsyncClient, token: str, *, complaint: str
) -> int:
    """Create a session with no Intake and no Summary row."""
    response = await client.post(
        "/api/chat/session",
        json={"initial_complaint": complaint},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


@pytest.mark.asyncio
async def test_document_only_session_preserves_lab_evidence(
    async_client: AsyncClient,
    db: AsyncSession,
) -> None:
    """Summary absent + document evidence present -> build succeeds, labs kept."""
    token, patient_id, _national_id = await _register_patient_async(
        async_client, seed="ctx-doc-only-labs"
    )
    session_id = await _create_bare_session(
        async_client, token, complaint="Lab results only"
    )

    # Real deterministic extraction — nothing about the payload is hand-authored.
    document = _text_layer_document(DOCUMENT_LINES)
    extraction = extract_clinical_values(document)
    assert not extraction.needs_review, extraction.review_reason
    assert any(
        value.name == "Hemoglobin" and value.value == "13.7"
        for value in extraction.values
    ), [(v.name, v.value) for v in extraction.values]

    payload = extraction.to_payload()
    db_file = FileModel(
        session_id=session_id,
        filename="pv-test-84721.pdf",
        s3_key=f"sessions/{session_id}/pv-test-84721.pdf",
        size_bytes=len(document.text.encode("utf-8")),
        content_type="application/pdf",
    )
    db.add(db_file)
    await db.flush()

    db.add(
        DocumentArtifact(
            session_id=session_id,
            file_id=db_file.id,
            kind=ArtifactKind.OCR,
            status=ArtifactStatus.SUCCEEDED,
            engine=document.engine,
            engine_version=document.engine_version,
            page_count=document.page_count,
            raw_text=document.text,
        )
    )
    db.add(
        DocumentArtifact(
            session_id=session_id,
            file_id=db_file.id,
            kind=ArtifactKind.EXTRACTION,
            status=ArtifactStatus.SUCCEEDED,
            engine=payload["method"],
            engine_version=payload["method_version"],
            page_count=document.page_count,
            payload_json=json.dumps(payload, ensure_ascii=False),
        )
    )
    await db.commit()

    context = await ClinicalContextBuilder().build(db, session_id)

    assert context.session_id == session_id
    assert context.patient_id == patient_id

    hemoglobin = [lab for lab in context.lab_evidence if lab.name == "Hemoglobin"]
    assert hemoglobin, [lab.name for lab in context.lab_evidence]
    assert "13.7" in (hemoglobin[0].extracted_data or "")

    assert context.document_evidence, "document evidence dropped"
    assert context.document_evidence[0].values, "extracted values dropped"

    # Fail-closed honesty: the placeholder summary invents nothing.
    assert not (context.summary.chief_complaint or "")
    assert context.summary.is_hpi_complete is False
    assert not context.summary.past_medical_history
    assert not context.summary.current_medications
    assert not context.summary.allergies
    assert not (context.summary.additional_notes or "")


@pytest.mark.asyncio
async def test_empty_session_still_fails_closed(
    async_client: AsyncClient,
    db: AsyncSession,
) -> None:
    """No summary and no evidence of any kind -> still refuses to build."""
    token, _patient_id, _national_id = await _register_patient_async(
        async_client, seed="ctx-empty-fail-closed"
    )
    session_id = await _create_bare_session(
        async_client, token, complaint="Nothing recorded yet"
    )

    with pytest.raises(ValueError, match="No clinical summary available"):
        await ClinicalContextBuilder().build(db, session_id)
