"""Tests for Fail-Closed on-demand document OCR endpoint."""

from __future__ import annotations

import asyncio
import io

import app.api.files as files_api_module
from tests.test_api_integration import (
    _async_client,
    _auth_headers,
    _create_session,
    _register_and_login_async,
    _save_layer1,
    _setup_test_db,
    _teardown,
)

STUB_EXTRACTED = "WBC: 4.5, Hb: 13.2, Plt: 150,000"


async def _seed_lab_with_ocr(
    client,
    headers: dict[str, str],
    *,
    seed: str,
    with_ocr: bool = True,
    link_condition: bool = True,
) -> tuple[int, int]:
    """Create session, lab slot, upload file. Returns (session_id, file_id)."""
    token_headers = headers
    session_id = await _create_session(client, token_headers)
    await _save_layer1(client, session_id, token_headers)

    layer4 = await client.post(
        f"/api/intake/{session_id}/layer4",
        json={"lab_results": [{"id": "lab-1", "name": "آزمایش خون CBC"}]},
        headers=token_headers,
    )
    assert layer4.status_code == 200, layer4.text

    data: dict[str, str] = {}
    if link_condition:
        data["condition_id"] = "lab-1"

    upload = await client.post(
        f"/api/files/{session_id}/upload",
        headers=token_headers,
        files={"file": ("cbc.png", io.BytesIO(b"fake-lab-image"), "image/png")},
        data=data or None,
    )
    assert upload.status_code == 200, upload.text
    file_id = upload.json()["id"]

    if with_ocr and link_condition:
        assert upload.json().get("extracted_data") == STUB_EXTRACTED

    return session_id, file_id


class TestDocumentOcrEndpoint:
    def test_returns_ocr_text_when_available(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(
            files_api_module,
            "extract_lab_values_ocr",
            lambda *_a, **_k: STUB_EXTRACTED,
        )

        async def _run() -> None:
            await _setup_test_db(tmp_path, monkeypatch)
            async with await _async_client() as client:
                token = await _register_and_login_async(
                    client, seed="DocOcrOk", password="VeryStrongPassword123!"
                )
                headers = _auth_headers(token)
                _session_id, file_id = await _seed_lab_with_ocr(client, headers, seed="DocOcrOk")

                res = await client.get(f"/api/documents/{file_id}/ocr", headers=headers)
                assert res.status_code == 200, res.text
                assert res.json()["ocr_text"] == STUB_EXTRACTED

        asyncio.run(_run())
        _teardown()

    def test_no_ocr_available_when_unlinked(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(
            files_api_module,
            "extract_lab_values_ocr",
            lambda *_a, **_k: STUB_EXTRACTED,
        )

        async def _run() -> None:
            await _setup_test_db(tmp_path, monkeypatch)
            async with await _async_client() as client:
                token = await _register_and_login_async(
                    client, seed="DocOcrUnlinked", password="VeryStrongPassword123!"
                )
                headers = _auth_headers(token)
                _session_id, file_id = await _seed_lab_with_ocr(
                    client, headers, seed="DocOcrUnlinked", link_condition=False
                )

                res = await client.get(f"/api/documents/{file_id}/ocr", headers=headers)
                assert res.status_code == 404, res.text
                assert res.json()["detail"] == "no_ocr_available"

        asyncio.run(_run())
        _teardown()

    def test_no_ocr_available_when_lab_has_no_extracted_data(
        self, tmp_path, monkeypatch
    ) -> None:
        def _stub_none(_file_bytes: bytes, _mime_type: str = "image/png") -> None:
            return None

        monkeypatch.setattr(files_api_module, "extract_lab_values_ocr", _stub_none)

        async def _run() -> None:
            await _setup_test_db(tmp_path, monkeypatch)
            async with await _async_client() as client:
                token = await _register_and_login_async(
                    client, seed="DocOcrEmpty", password="VeryStrongPassword123!"
                )
                headers = _auth_headers(token)
                _session_id, file_id = await _seed_lab_with_ocr(
                    client, headers, seed="DocOcrEmpty", with_ocr=False
                )

                res = await client.get(f"/api/documents/{file_id}/ocr", headers=headers)
                assert res.status_code == 404, res.text
                assert res.json()["detail"] == "no_ocr_available"

        asyncio.run(_run())
        _teardown()

    def test_unauthorized_returns_not_found_without_leaking(
        self, tmp_path, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            files_api_module,
            "extract_lab_values_ocr",
            lambda *_a, **_k: STUB_EXTRACTED,
        )

        async def _run() -> None:
            await _setup_test_db(tmp_path, monkeypatch)
            async with await _async_client() as client:
                owner_token = await _register_and_login_async(
                    client, seed="DocOcrOwner", password="VeryStrongPassword123!"
                )
                owner_headers = _auth_headers(owner_token)
                _session_id, file_id = await _seed_lab_with_ocr(
                    client, owner_headers, seed="DocOcrOwner"
                )

                other_token = await _register_and_login_async(
                    client, seed="DocOcrOther", password="VeryStrongPassword123!"
                )
                other_headers = _auth_headers(other_token)

                res = await client.get(
                    f"/api/documents/{file_id}/ocr", headers=other_headers
                )
                assert res.status_code == 404, res.text
                assert res.json()["detail"] == "not_found"

                missing = await client.get(
                    "/api/documents/999999/ocr", headers=owner_headers
                )
                assert missing.status_code == 404, missing.text
                assert missing.json()["detail"] == "not_found"

        asyncio.run(_run())
        _teardown()

    def test_session_scoped_resolution_ignores_other_session_labs(
        self, tmp_path, monkeypatch
    ) -> None:
        """Same condition_id in another session must not leak OCR."""
        monkeypatch.setattr(
            files_api_module,
            "extract_lab_values_ocr",
            lambda *_a, **_k: STUB_EXTRACTED,
        )

        async def _run() -> None:
            await _setup_test_db(tmp_path, monkeypatch)
            async with await _async_client() as client:
                token_a = await _register_and_login_async(
                    client, seed="DocOcrSessA", password="VeryStrongPassword123!"
                )
                headers_a = _auth_headers(token_a)
                _sid_a, file_a = await _seed_lab_with_ocr(
                    client, headers_a, seed="DocOcrSessA"
                )

                token_b = await _register_and_login_async(
                    client, seed="DocOcrSessB", password="VeryStrongPassword123!"
                )
                headers_b = _auth_headers(token_b)
                session_b = await _create_session(client, headers_b)
                layer1_b = await _save_layer1(
                    client,
                    session_b,
                    headers_b,
                    payload={
                        "first_name": "سارا",
                        "last_name": "محمدی",
                        "national_id": "0013542419",
                        "insurance_provider": "تامین اجتماعی",
                        "age": 30,
                        "sex": "female",
                        "weight": 60.0,
                        "height": 165.0,
                        "chief_complaint": "خستگی",
                    },
                )
                assert layer1_b.status_code == 200, layer1_b.text
                layer4_b = await client.post(
                    f"/api/intake/{session_b}/layer4",
                    json={
                        "lab_results": [
                            {"id": "lab-1", "name": "CBC without OCR"},
                        ],
                    },
                    headers=headers_b,
                )
                assert layer4_b.status_code == 200, layer4_b.text

                # File from session A must not be readable by B
                res = await client.get(
                    f"/api/documents/{file_a}/ocr", headers=headers_b
                )
                assert res.status_code == 404
                assert res.json()["detail"] == "not_found"

                # Upload for B linked to lab-1 but OCR stub still runs — B can read own
                upload_b = await client.post(
                    f"/api/files/{session_b}/upload",
                    headers=headers_b,
                    files={"file": ("b.png", io.BytesIO(b"img"), "image/png")},
                    data={"condition_id": "lab-1"},
                )
                assert upload_b.status_code == 200, upload_b.text
                file_b = upload_b.json()["id"]
                res_b = await client.get(
                    f"/api/documents/{file_b}/ocr", headers=headers_b
                )
                assert res_b.status_code == 200
                assert res_b.json()["ocr_text"] == STUB_EXTRACTED

        asyncio.run(_run())
        _teardown()
