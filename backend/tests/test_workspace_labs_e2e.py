"""Runtime E2E: uploaded document → real pipeline → Clinical Content → Workspace.

This exercises the *actual application path*. Specifically it does NOT:

* call ``extract_clinical_values`` directly,
* construct ``lab_evidence`` by hand,
* insert DocumentArtifact rows by hand,
* override ``resolve_clinical_context`` / ``resolve_clinical_content_inputs``,
* mock the clinical-content or workspace response,
* or bypass authentication or authorization.

The document is uploaded over real HTTP multipart to the real
``POST /api/files/{session_id}/upload`` route; the application's own background
processing produces the OCR and extraction artifacts; a real doctor account
authenticates and reads the real ``clinical-content`` and ``workspace``
endpoints.

Documented infrastructure substitutions (non-clinical only, both supplied by the
repository's own test harness):

* **Object storage** — ``conftest.patch_fake_storage`` swaps S3/MinIO for an
  in-memory store. ``document_pipeline`` binds ``storage_service`` at import, so
  this test re-points that reference at the *same* store the upload API wrote to.
  Without it the pipeline would try to reach MinIO. The bytes read back are the
  exact bytes uploaded.
* **Database** — SQLite via ``conftest`` (``TEST_DATABASE_URL`` unset).

Nothing on the clinical path is mocked: OCR/text-extraction, clinical
extraction, artifact persistence, ClinicalContextBuilder, the projection, and
both HTTP endpoints all execute for real.
"""

from __future__ import annotations

import io
import json
import os

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.api.files as files_api_module
import app.services.document_pipeline as document_pipeline_module
from app.models import ArtifactKind, DocumentArtifact
from tests.test_soap_clinical_context import _register_patient_async

#: Contents of the synthetic verification artifact. The expected clinical value
#: lives ONLY here, in the test artifact — never in production code.
DOCUMENT_LINES = (
    "CBC Laboratory Report",
    "Patient ID: PV-TEST-84721",
    "Date: 2026-08-20",
    "Hemoglobin: 13.7 g/dL",
    "WBC: 8,421 /uL",
    "Platelets: 245,000 /uL",
)

EXPECTED_ANALYTE = "Hemoglobin"
EXPECTED_VALUE = "13.7"
EXPECTED_UNIT = "g/dL"


def _build_text_layer_pdf(lines: tuple[str, ...]) -> bytes:
    """Assemble a minimal single-page PDF that carries a real text layer.

    Hand-assembled so the test adds no PDF-authoring dependency. Only the
    *artifact* is synthetic — the application still does all the reading of it
    (``file_processor.extract_text_from_pdf`` → pypdf). A text layer is used
    deliberately: ``run_document_ocr`` tries it before rasterisation, so this
    path needs neither Tesseract nor Poppler.
    """
    parts = ["BT", "/F1 12 Tf"]
    y = 720
    for line in lines:
        escaped = (
            line.replace("\\", "\\\\").replace("(", r"\(").replace(")", r"\)")
        )
        parts.append(f"1 0 0 1 72 {y} Tm ({escaped}) Tj")
        y -= 20
    parts.append("ET")
    content = "\n".join(parts).encode("latin-1")

    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        (
            b"<< /Length "
            + str(len(content)).encode("ascii")
            + b" >>\nstream\n"
            + content
            + b"\nendstream"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for index, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode("ascii") + body + b"\nendobj\n"

    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode("ascii")
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode("ascii")
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_at}\n%%EOF\n"
    ).encode("ascii")
    return bytes(out)


async def _open_session(client: AsyncClient, headers: dict[str, str]) -> int:
    response = await client.post(
        "/api/chat/session",
        json={"initial_complaint": "Lab results"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


async def _login_doctor(client: AsyncClient) -> dict[str, str]:
    """Authenticate as the harness-seeded doctor via the real login endpoint."""
    username = os.environ.get("SEED_DOCTOR_USERNAME", "bagherzade")
    password = os.environ["SEED_DOCTOR_PASSWORD"]
    response = await client.post(
        "/api/auth/login",
        json={"national_id": username, "password": password},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("access_token"), body
    return {"Authorization": f"Bearer {body['access_token']}"}


@pytest.mark.asyncio
async def test_uploaded_document_reaches_workspace_labs(
    async_client: AsyncClient,
    db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Infrastructure only: aim the pipeline at the same in-memory object store
    # the upload API writes to (see module docstring).
    monkeypatch.setattr(
        document_pipeline_module, "storage_service", files_api_module.storage_service
    )

    token, patient_id, _national_id = await _register_patient_async(
        async_client, seed="e2e-workspace-labs"
    )
    patient_headers = {"Authorization": f"Bearer {token}"}
    session_id = await _open_session(async_client, patient_headers)

    # ---- real multipart upload of the verification artifact -----------------
    pdf_bytes = _build_text_layer_pdf(DOCUMENT_LINES)
    upload = await async_client.post(
        f"/api/files/{session_id}/upload",
        headers=patient_headers,
        files={
            "file": ("pv-test-84721.pdf", io.BytesIO(pdf_bytes), "application/pdf")
        },
    )
    print(f"\n[UPLOAD] status={upload.status_code} body={upload.text}")
    assert upload.status_code == 200, upload.text
    file_id = upload.json()["id"]

    # ---- artifacts produced by the application's own pipeline ---------------
    await db.rollback()  # fresh read snapshot; the app committed on its own session
    artifacts = (
        (
            await db.execute(
                select(DocumentArtifact).where(DocumentArtifact.file_id == file_id)
            )
        )
        .scalars()
        .all()
    )
    print(
        "[ARTIFACTS] "
        + json.dumps(
            [
                {
                    "kind": a.kind,
                    "status": a.status,
                    "engine": a.engine,
                    "error": a.error_detail,
                }
                for a in artifacts
            ],
            ensure_ascii=False,
        )
    )
    by_kind = {a.kind: a for a in artifacts}
    assert ArtifactKind.OCR in by_kind, "no OCR artifact produced"
    assert ArtifactKind.EXTRACTION in by_kind, "no EXTRACTION artifact produced"

    ocr = by_kind[ArtifactKind.OCR]
    print(f"[OCR] engine={ocr.engine} status={ocr.status} text={ocr.raw_text!r}")
    assert ocr.raw_text and EXPECTED_VALUE in ocr.raw_text

    extraction = by_kind[ArtifactKind.EXTRACTION]
    payload = json.loads(extraction.payload_json or "{}")
    print(
        f"[EXTRACTION] status={extraction.status} engine={extraction.engine} "
        + json.dumps(payload.get("values", []), ensure_ascii=False)
    )
    extracted = [
        value for value in payload.get("values", []) if value["name"] == EXPECTED_ANALYTE
    ]
    assert extracted, payload.get("values")
    assert extracted[0]["value"] == EXPECTED_VALUE
    assert extracted[0]["unit"] == EXPECTED_UNIT
    assert extracted[0]["needs_review"] is False

    # ---- real doctor authentication ----------------------------------------
    doctor_headers = await _login_doctor(async_client)

    # ---- real Clinical Content API (real builder, no dependency override) ---
    content = await async_client.get(
        f"/api/sessions/{session_id}/clinical-content", headers=doctor_headers
    )
    print(f"[CLINICAL-CONTENT] status={content.status_code}")
    assert content.status_code == 200, content.text
    labs = content.json()["content"]["labs"]
    print("[CLINICAL-CONTENT labs] " + json.dumps(labs, ensure_ascii=False))
    assert labs is not None, "labs section absent from clinical-content"
    rows = [row for row in labs["rows"] if row["name"] == EXPECTED_ANALYTE]
    assert rows, labs["rows"]
    assert EXPECTED_VALUE in rows[0]["value"], rows[0]

    # ---- real Workspace API ------------------------------------------------
    workspace = await async_client.get(
        f"/api/sessions/{session_id}/workspace", headers=doctor_headers
    )
    print(
        f"[WORKSPACE] status={workspace.status_code} "
        f"etag={workspace.headers.get('ETag')} "
        f"contract={workspace.headers.get('X-Contract-Version')}"
    )
    assert workspace.status_code == 200, workspace.text
    plan = workspace.json()
    directives = [
        d for d in plan["layout_directives"] if d["object_id"] == "labs"
    ]
    print("[WORKSPACE labs directive] " + json.dumps(directives, ensure_ascii=False))
    assert directives, [d["object_id"] for d in plan["layout_directives"]]
    assert directives[0]["slot"] != "hidden", directives[0]


@pytest.mark.asyncio
async def test_empty_session_clinical_content_fails_closed(
    async_client: AsyncClient,
) -> None:
    """The safety boundary must survive the BREAK C repair, via the real API."""
    token, _patient_id, _national_id = await _register_patient_async(
        async_client, seed="e2e-fail-closed"
    )
    session_id = await _open_session(
        async_client, {"Authorization": f"Bearer {token}"}
    )

    doctor_headers = await _login_doctor(async_client)
    response = await async_client.get(
        f"/api/sessions/{session_id}/clinical-content", headers=doctor_headers
    )
    print(f"\n[FAIL-CLOSED] status={response.status_code} body={response.text}")
    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "WORKSPACE_SESSION_NOT_FOUND"
