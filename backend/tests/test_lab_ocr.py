import asyncio
import io

import app.api.files as files_api_module
from app.schemas.intake import MedicalOverview
from app.services.medical_overview_service import (
    is_lab_bind_id,
    validate_condition_id,
)
from app.services.ocr_service import extract_lab_values_ocr
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


def test_extract_lab_values_ocr_returns_none_for_invalid_bytes() -> None:
    assert extract_lab_values_ocr(b"fake-image-bytes") is None


def test_medical_overview_accepts_lab_results() -> None:
    overview = MedicalOverview(
        lab_results=[
            {"id": "lab-1", "name": "آزمایش خون CBC"},
            {"id": "lab-2", "name": "آزمایش تیروئید", "extracted_data": STUB_EXTRACTED},
        ]
    )
    assert len(overview.lab_results) == 2
    assert overview.lab_results[1].extracted_data == STUB_EXTRACTED


def test_validate_condition_id_accepts_lab_ids() -> None:
    overview = MedicalOverview(
        chronic_conditions=[{"id": "cond-1", "name": "دیابت", "duration": ""}],
        lab_results=[{"id": "lab-1", "name": "CBC"}],
    )
    assert validate_condition_id(overview, "cond-1") is True
    assert validate_condition_id(overview, "lab-1") is True
    assert validate_condition_id(overview, "med-bind-uuid") is True


def test_is_lab_bind_id() -> None:
    overview = MedicalOverview(lab_results=[{"id": "lab-1", "name": "CBC"}])
    assert is_lab_bind_id(overview, "lab-1") is True
    assert is_lab_bind_id(overview, "cond-1") is False
    assert is_lab_bind_id(None, "lab-1") is False


class TestLabOcrUpload:
    def test_lab_upload_triggers_ocr_and_persists_extracted_data(self, tmp_path, monkeypatch) -> None:
        def _stub_ocr(_file_bytes: bytes, _mime_type: str = "image/png") -> str:
            return STUB_EXTRACTED

        monkeypatch.setattr(files_api_module, "extract_lab_values_ocr", _stub_ocr)

        async def _run() -> None:
            await _setup_test_db(tmp_path, monkeypatch)
            async with await _async_client() as client:
                token = await _register_and_login_async(
                    client,
                    seed="LabOcr",
                    password="VeryStrongPassword123!",
                )
                headers = _auth_headers(token)
                session_id = await _create_session(client, headers)
                await _save_layer1(client, session_id, headers)

                layer4 = await client.post(
                    f"/api/intake/{session_id}/layer4",
                    json={
                        "lab_results": [
                            {"id": "lab-1", "name": "آزمایش خون CBC"},
                        ],
                    },
                    headers=headers,
                )
                assert layer4.status_code == 200, layer4.text

                upload = await client.post(
                    f"/api/files/{session_id}/upload",
                    headers=headers,
                    files={"file": ("cbc.png", io.BytesIO(b"fake-lab-image"), "image/png")},
                    data={"condition_id": "lab-1"},
                )
                assert upload.status_code == 200, upload.text
                body = upload.json()
                assert body["condition_id"] == "lab-1"
                assert body["extracted_data"] == STUB_EXTRACTED

                intake = await client.get(f"/api/intake/{session_id}", headers=headers)
                assert intake.status_code == 200, intake.text
                lab_results = intake.json()["medical_overview"]["lab_results"]
                assert len(lab_results) == 1
                assert lab_results[0]["id"] == "lab-1"
                # Fail-Closed: OCR stripped from intake payloads
                assert not lab_results[0].get("extracted_data")

                file_id = body["id"]
                ocr = await client.get(f"/api/documents/{file_id}/ocr", headers=headers)
                assert ocr.status_code == 200, ocr.text
                assert ocr.json()["ocr_text"] == STUB_EXTRACTED

        asyncio.run(_run())
        _teardown()

    def test_lab_upload_succeeds_when_ocr_raises(self, tmp_path, monkeypatch) -> None:
        def _boom(_file_bytes: bytes, _mime_type: str = "image/png") -> str:
            raise RuntimeError("OCR boom")

        monkeypatch.setattr(files_api_module, "extract_lab_values_ocr", _boom)

        async def _run() -> None:
            await _setup_test_db(tmp_path, monkeypatch)
            async with await _async_client() as client:
                token = await _register_and_login_async(
                    client,
                    seed="LabOcrFail",
                    password="VeryStrongPassword123!",
                )
                headers = _auth_headers(token)
                session_id = await _create_session(client, headers)
                await _save_layer1(client, session_id, headers)

                layer4 = await client.post(
                    f"/api/intake/{session_id}/layer4",
                    json={
                        "lab_results": [
                            {"id": "lab-1", "name": "آزمایش خون CBC"},
                        ],
                    },
                    headers=headers,
                )
                assert layer4.status_code == 200, layer4.text

                upload = await client.post(
                    f"/api/files/{session_id}/upload",
                    headers=headers,
                    files={"file": ("cbc.png", io.BytesIO(b"fake-lab-image"), "image/png")},
                    data={"condition_id": "lab-1"},
                )
                assert upload.status_code == 200, upload.text
                body = upload.json()
                assert body["condition_id"] == "lab-1"
                assert "extracted_data" not in body
                file_id = body["id"]

                listed = await client.get(f"/api/files/{session_id}/list", headers=headers)
                assert listed.status_code == 200, listed.text
                listed_files = listed.json()
                assert len(listed_files) == 1
                assert listed_files[0]["id"] == file_id

        asyncio.run(_run())
        _teardown()

    def test_lab_pdf_upload_triggers_ocr(self, tmp_path, monkeypatch) -> None:
        def _stub_ocr(_file_bytes: bytes, mime_type: str) -> str:
            assert mime_type == "application/pdf"
            return STUB_EXTRACTED

        monkeypatch.setattr(files_api_module, "extract_lab_values_ocr", _stub_ocr)

        async def _run() -> None:
            await _setup_test_db(tmp_path, monkeypatch)
            async with await _async_client() as client:
                token = await _register_and_login_async(
                    client,
                    seed="LabPdfOcr",
                    password="VeryStrongPassword123!",
                )
                headers = _auth_headers(token)
                session_id = await _create_session(client, headers)
                await _save_layer1(client, session_id, headers)

                layer4 = await client.post(
                    f"/api/intake/{session_id}/layer4",
                    json={
                        "lab_results": [
                            {"id": "lab-1", "name": "آزمایش خون CBC"},
                        ],
                    },
                    headers=headers,
                )
                assert layer4.status_code == 200, layer4.text

                upload = await client.post(
                    f"/api/files/{session_id}/upload",
                    headers=headers,
                    files={
                        "file": (
                            "cbc.pdf",
                            io.BytesIO(b"%PDF-1.4 fake"),
                            "application/pdf",
                        )
                    },
                    data={"condition_id": "lab-1"},
                )
                assert upload.status_code == 200, upload.text
                body = upload.json()
                assert body["condition_id"] == "lab-1"
                assert body["extracted_data"] == STUB_EXTRACTED

        asyncio.run(_run())
        _teardown()

    def test_lab_upload_with_condition_type_before_layer4_save(
        self, tmp_path, monkeypatch
    ) -> None:
        lab_calls: list[tuple[bytes, str]] = []
        med_calls: list[tuple[bytes, str]] = []

        def _stub_lab(file_bytes: bytes, mime_type: str = "image/png") -> str:
            lab_calls.append((file_bytes, mime_type))
            return STUB_EXTRACTED

        def _stub_med(file_bytes: bytes, mime_type: str) -> list[dict[str, str]] | None:
            med_calls.append((file_bytes, mime_type))
            return [{"name": "Losartan", "amount": "۱ عدد", "frequency": "روزی ۱ بار"}]

        monkeypatch.setattr(files_api_module, "extract_lab_values_ocr", _stub_lab)
        monkeypatch.setattr(files_api_module, "extract_medication_ocr", _stub_med)

        async def _run() -> None:
            await _setup_test_db(tmp_path, monkeypatch)
            async with await _async_client() as client:
                token = await _register_and_login_async(
                    client,
                    seed="LabTypeOcr",
                    password="VeryStrongPassword123!",
                )
                headers = _auth_headers(token)
                session_id = await _create_session(client, headers)
                await _save_layer1(client, session_id, headers)

                lab_id = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
                upload = await client.post(
                    f"/api/files/{session_id}/upload",
                    headers=headers,
                    files={"file": ("cbc.png", io.BytesIO(b"fake-lab-image"), "image/png")},
                    data={"condition_id": lab_id, "condition_type": "lab"},
                )
                assert upload.status_code == 200, upload.text
                body = upload.json()
                assert body["condition_id"] == lab_id
                assert body["extracted_data"] == STUB_EXTRACTED
                assert "extracted_medications" not in body
                assert len(lab_calls) == 1
                assert len(med_calls) == 0

        asyncio.run(_run())
        _teardown()

    def test_image_upload_without_condition_type_skips_ocr(
        self, tmp_path, monkeypatch
    ) -> None:
        lab_calls: list[tuple[bytes, str]] = []
        med_calls: list[tuple[bytes, str]] = []

        def _stub_lab(file_bytes: bytes, mime_type: str = "image/png") -> str:
            lab_calls.append((file_bytes, mime_type))
            return STUB_EXTRACTED

        def _stub_med(file_bytes: bytes, mime_type: str) -> list[dict[str, str]] | None:
            med_calls.append((file_bytes, mime_type))
            return [{"name": "Losartan", "amount": "۱ عدد", "frequency": "روزی ۱ بار"}]

        monkeypatch.setattr(files_api_module, "extract_lab_values_ocr", _stub_lab)
        monkeypatch.setattr(files_api_module, "extract_medication_ocr", _stub_med)

        async def _run() -> None:
            await _setup_test_db(tmp_path, monkeypatch)
            async with await _async_client() as client:
                token = await _register_and_login_async(
                    client,
                    seed="NoTypeOcr",
                    password="VeryStrongPassword123!",
                )
                headers = _auth_headers(token)
                session_id = await _create_session(client, headers)
                await _save_layer1(client, session_id, headers)

                unknown_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
                upload = await client.post(
                    f"/api/files/{session_id}/upload",
                    headers=headers,
                    files={"file": ("unknown.png", io.BytesIO(b"fake-image"), "image/png")},
                    data={"condition_id": unknown_id},
                )
                assert upload.status_code == 200, upload.text
                body = upload.json()
                assert body["condition_id"] == unknown_id
                assert "extracted_data" not in body
                assert "extracted_medications" not in body
                assert len(lab_calls) == 0
                assert len(med_calls) == 0

        asyncio.run(_run())
        _teardown()
