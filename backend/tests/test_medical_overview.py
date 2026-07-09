import asyncio
import io
from unittest.mock import AsyncMock

import app.api.intake as intake_api
from app.schemas.intake import ClinicalSummary, HPIQuestionsResponse
from app.services.intake_llm import ClinicalSummaryResult, Layer2GenerationResult
from app.services.medical_overview_service import normalize_legacy_medical_history
from tests.test_api_integration import (
    _async_client,
    _auth_headers,
    _clinical_summary_result,
    _create_session,
    _layer2_result,
    _register_and_login_async,
    _save_layer1,
    _setup_test_db,
    _teardown,
)
from tests.test_mvp_flow import _national_id_from_seed


def test_normalize_legacy_medical_history_maps_old_keys() -> None:
    overview = normalize_legacy_medical_history(
        {
            "allergy_history": ["پنی‌سیلین", "آسپرین"],
            "past_surgical_history": ["آپاندکتومی"],
            "family_history": ["دیابت"],
            "past_medical_history": ["فشار خون", "هیچ‌کدام"],
        }
    )

    assert overview.allergies == "پنی‌سیلین، آسپرین"
    assert overview.surgical_history == "آپاندکتومی"
    assert overview.family_history == "دیابت"
    assert len(overview.chronic_conditions) == 1
    assert overview.chronic_conditions[0].name == "فشار خون"


class TestMedicalOverviewIntegration:
    def test_intake_submit_syncs_patient_overview(self, tmp_path, monkeypatch) -> None:
        async def _run() -> None:
            await _setup_test_db(tmp_path, monkeypatch)
            async with await _async_client() as client:
                national_id = _national_id_from_seed("OverviewSync")
                register = await client.post(
                    "/api/auth/register",
                    json={
                        "national_id": national_id,
                        "password": "VeryStrongPassword123!",
                        "role": "patient",
                    },
                )
                assert register.status_code == 200, register.text
                patient_id = register.json()["id"]

                login = await client.post(
                    "/api/auth/login",
                    json={
                        "national_id": national_id,
                        "password": "VeryStrongPassword123!",
                    },
                )
                assert login.status_code == 200, login.text
                headers = _auth_headers(login.json()["access_token"])
                session_id = await _create_session(client, headers)
                await _save_layer1(client, session_id, headers)

                monkeypatch.setattr(
                    intake_api.intake_llm_service,
                    "generate_hpi_questions",
                    AsyncMock(
                        return_value=_layer2_result(
                            HPIQuestionsResponse(
                                question_strategy="Acute",
                                questions=[
                                    {
                                        "id": "onset",
                                        "question": "Q",
                                        "priority": 1,
                                        "red_flag_related": False,
                                    }
                                ],
                            )
                        )
                    ),
                )
                monkeypatch.setattr(
                    intake_api.intake_llm_service,
                    "generate_clinical_summary",
                    AsyncMock(
                        return_value=_clinical_summary_result(
                            ClinicalSummary(
                                chief_complaint="دل درد",
                                hpi_summary="خلاصه",
                                pertinent_positives=[],
                                pertinent_negatives=[],
                                red_flags=[],
                            )
                        )
                    ),
                )

                await client.post(f"/api/intake/{session_id}/layer2/generate", headers=headers)
                await client.post(
                    f"/api/intake/{session_id}/layer2/answer",
                    json={"question_id": "onset", "answer": "دیروز"},
                    headers=headers,
                )
                await client.post(f"/api/intake/{session_id}/layer3/generate", headers=headers)

                overview_payload = {
                    "allergies": "پنی‌سیلین",
                    "chronic_conditions": [
                        {"id": "cond-1", "name": "دیابت", "duration": "۵ سال"},
                    ],
                    "current_medications": ["متفورمین"],
                }
                layer4 = await client.post(
                    f"/api/intake/{session_id}/layer4",
                    json=overview_payload,
                    headers=headers,
                )
                assert layer4.status_code == 200, layer4.text

                submit = await client.post(
                    f"/api/intake/{session_id}/submit",
                    headers=headers,
                )
                assert submit.status_code == 200, submit.text

                overview_get = await client.get(
                    f"/api/pmh/overview/{patient_id}",
                    headers=headers,
                )
                assert overview_get.status_code == 200, overview_get.text
                assert overview_get.json()["overview"]["chronic_conditions"][0]["name"] == "دیابت"

                summary = await client.get(f"/api/summary/{session_id}", headers=headers)
                assert summary.status_code == 200, summary.text
                body = summary.json()
                assert body["clinical_overview"]["drug_history"] == ["متفورمین"]
                assert body["clinical_overview"]["chronic_conditions"][0]["name"] == "دیابت"
                assert body["soap_status"] == "pending"

        asyncio.run(_run())
        _teardown()

    def test_file_upload_and_link_to_condition(self, tmp_path, monkeypatch) -> None:
        async def _run() -> None:
            await _setup_test_db(tmp_path, monkeypatch)
            async with await _async_client() as client:
                token = await _register_and_login_async(
                    client,
                    seed="FileLink",
                    password="VeryStrongPassword123!",
                )
                headers = _auth_headers(token)
                session_id = await _create_session(client, headers)
                await _save_layer1(client, session_id, headers)

                overview_payload = {
                    "chronic_conditions": [
                        {"id": "cond-lab", "name": "دیابت", "duration": "۲ سال"},
                    ],
                }
                await client.post(
                    f"/api/intake/{session_id}/layer4",
                    json=overview_payload,
                    headers=headers,
                )

                upload = await client.post(
                    f"/api/files/{session_id}/upload",
                    headers=headers,
                    files={"file": ("lab.png", io.BytesIO(b"fake-image"), "image/png")},
                    data={"condition_id": "cond-lab"},
                )
                assert upload.status_code == 200, upload.text
                file_id = upload.json()["id"]
                assert upload.json()["condition_id"] == "cond-lab"

                listed = await client.get(f"/api/files/{session_id}/list", headers=headers)
                assert listed.status_code == 200
                assert listed.json()[0]["condition_id"] == "cond-lab"

                patch = await client.patch(
                    f"/api/files/{session_id}/files/{file_id}",
                    json={"condition_id": None},
                    headers=headers,
                )
                assert patch.status_code == 200
                assert patch.json()["condition_id"] is None

        asyncio.run(_run())
        _teardown()

    def test_medication_image_upload_returns_extracted_medications_null(
        self, tmp_path, monkeypatch
    ) -> None:
        async def _run() -> None:
            await _setup_test_db(tmp_path, monkeypatch)
            async with await _async_client() as client:
                token = await _register_and_login_async(
                    client,
                    seed="MedOCR",
                    password="VeryStrongPassword123!",
                )
                headers = _auth_headers(token)
                session_id = await _create_session(client, headers)
                await _save_layer1(client, session_id, headers)

                med_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
                overview_payload = {
                    "current_medications": [
                        {
                            "id": med_id,
                            "name": "",
                            "amount": "",
                            "frequency": "",
                        }
                    ],
                }
                layer4 = await client.post(
                    f"/api/intake/{session_id}/layer4",
                    json=overview_payload,
                    headers=headers,
                )
                assert layer4.status_code == 200, layer4.text

                upload = await client.post(
                    f"/api/files/{session_id}/upload",
                    headers=headers,
                    files={"file": ("pillbox.png", io.BytesIO(b"fake-image"), "image/png")},
                    data={"condition_id": med_id},
                )
                assert upload.status_code == 200, upload.text
                body = upload.json()
                assert body["condition_id"] == med_id
                assert "extracted_medications" in body
                assert body["extracted_medications"] is None

        asyncio.run(_run())
        _teardown()
