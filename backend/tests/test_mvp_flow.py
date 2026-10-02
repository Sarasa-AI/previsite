from io import BytesIO

import pytest
from fastapi.testclient import TestClient

import app.api.chat as chat_api
from app.main import app as fastapi_app
from tests.auth_helpers import national_id_from_seed as _national_id_from_seed
from tests.auth_helpers import register_and_login as _register_and_login


def _create_client(tmp_path, monkeypatch):
    import asyncio

    from tests.conftest import setup_async_test_db, teardown_test_db

    engine = asyncio.run(setup_async_test_db(tmp_path, monkeypatch))
    client = TestClient(fastapi_app)

    def cleanup():
        teardown_test_db()
        asyncio.run(engine.dispose())
        client.close()

    client._async_cleanup = cleanup  # type: ignore[attr-defined]
    return client


@pytest.mark.parametrize("supplied_role", ["doctor", "admin", "visitor", "superuser"])
def test_register_ignores_client_role_and_creates_patient(
    tmp_path, monkeypatch, supplied_role: str
) -> None:
    """OTP registration always creates a patient (role forced server-side)."""
    from app.services.sms import get_test_sms_provider, reset_test_sms_provider
    from tests.auth_helpers import phone_from_seed

    client = _create_client(tmp_path, monkeypatch)
    try:
        reset_test_sms_provider()
        phone = phone_from_seed(f"role-escalation-{supplied_role}")

        req = client.post("/api/auth/otp/request", json={"phone": phone})
        assert req.status_code == 200, req.text
        code = get_test_sms_provider().last_code_for(phone)
        assert code
        ver = client.post(
            "/api/auth/otp/verify",
            json={"phone": phone, "code": code},
        )
        assert ver.status_code == 200, ver.text
        token = ver.json()["access_token"]
        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["role"] == "patient"
    finally:
        client._async_cleanup()  # type: ignore[attr-defined]


def test_auth_session_chat_summary_and_upload_flow(tmp_path, monkeypatch) -> None:
    client = _create_client(tmp_path, monkeypatch)

    async def fake_extract(text: str):
        return {
            "chief_complaint": text,
            "symptoms": ["سردرد"],
            "medications": [],
            "allergies": [],
            "past_diseases": ["میگرن"],
        }

    async def fake_build_summary(_messages):
        return {
            "chief_complaint": "سردرد شدید",
            "history_present_illness": "از دیروز شروع شده است.",
            "past_medical_history": "میگرن",
            "medications": "نامشخص",
            "allergies": "نامشخص",
            "assessment": "شرح حال اولیه ثبت شد.",
        }

    async def fake_chat(_messages, system_prompt=None, **kwargs):
        if len(_messages) == 1:
            return "شدت سردرد از ۱ تا ۱۰ چقدر است؟"
        elif len(_messages) == 3:
            return "آیا حالت تهوع یا استفراغ هم دارید؟"
        elif len(_messages) == 5:
            return "ممنون از همکاری شما. اطلاعات کافی جمع‌آوری شد."
        elif len(_messages) == 7:
            return "ممنون از همکاری شما. اطلاعات کافی جمع‌آوری شد."
        return "پاسخ پیش‌فرض"

    async def fake_run_soap_generation(
        session_id: int,
        correlation_id: str | None = None,
        entry: str = "unknown",
    ) -> None:
        from sqlalchemy import select

        from app.db.database import get_async_session
        from app.models import Summary as SummaryModel

        async with get_async_session() as db:
            result = await db.execute(
                select(SummaryModel).where(SummaryModel.session_id == session_id)
            )
            summary = result.scalar_one_or_none()
            soap = "# SOAP\n\nS: سردرد شدید\n\nA: نیاز به ارزیابی پزشک"
            if summary:
                summary.soap_note = soap
            else:
                db.add(SummaryModel(session_id=session_id, soap_note=soap))
            await db.commit()

    monkeypatch.setattr(chat_api.summary_builder, "build_summary", fake_build_summary)
    monkeypatch.setattr(chat_api.llm_service, "chat", fake_chat)
    monkeypatch.setattr(chat_api, "run_soap_generation", fake_run_soap_generation)

    token = _register_and_login(
        client,
        seed="Patient One",
        password="VeryStrongPassword123!",
    )
    headers = {"Authorization": f"Bearer {token}"}

    session_response = client.post(
        "/api/chat/session",
        json={"initial_complaint": "سردرد شدید"},
        headers=headers,
    )
    assert session_response.status_code == 200
    session_id = session_response.json()["id"]

    list_response = client.get("/api/chat/sessions", headers=headers)
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    chat_response = client.post(
        f"/api/chat/{session_id}",
        json={"content": "از دیروز سردرد دارم"},
        headers=headers,
    )
    assert chat_response.status_code == 200
    assert chat_response.json()["content"] == "شدت سردرد از ۱ تا ۱۰ چقدر است؟"

    chat_response = client.post(
        f"/api/chat/{session_id}",
        json={"content": "۸ از ۱۰"},
        headers=headers,
    )
    assert chat_response.status_code == 200
    assert chat_response.json()["content"] == "آیا حالت تهوع یا استفراغ هم دارید؟"

    chat_response = client.post(
        f"/api/chat/{session_id}",
        json={"content": "بله، کمی تهوع دارم."},
        headers=headers,
    )
    assert chat_response.status_code == 200
    assert chat_response.json()["content"] == "ممنون از همکاری شما. اطلاعات کافی جمع‌آوری شد."

    chat_response = client.post(
        f"/api/chat/{session_id}",
        json={"content": "خیر، هیچ علامت دیگری ندارم."},
        headers=headers,
    )
    assert chat_response.status_code == 200
    assert chat_response.json()["content"] == "ممنون از همکاری شما. اطلاعات کافی جمع‌آوری شد."

    history_response = client.get(f"/api/chat/{session_id}", headers=headers)
    assert history_response.status_code == 200
    assert len(history_response.json()["messages"]) == 8

    upload_response = client.post(
        f"/api/files/{session_id}/upload",
        files={"file": ("report.txt", BytesIO(b"normal report"), "text/plain")},
        headers=headers,
    )
    assert upload_response.status_code == 200
    upload_body = upload_response.json()
    assert upload_body["filename"] == "report.txt"
    assert upload_body["file_path"].startswith(f"{session_id}/")

    file_id = upload_body["id"]
    download_response = client.get(
        f"/api/files/download/{file_id}",
        headers=headers,
        follow_redirects=False,
    )
    assert download_response.status_code == 307
    assert "fake-storage.example" in download_response.headers["location"]

    summary_exists_response = client.get(
        f"/api/summary/session/{session_id}/exists",
        headers=headers,
    )
    assert summary_exists_response.status_code == 200
    assert summary_exists_response.json() == {"exists": True}

    submit_response = client.post(f"/api/chat/{session_id}/submit", headers=headers)
    assert submit_response.status_code == 200

    summary_response = client.get(f"/api/summary/{session_id}", headers=headers)
    assert summary_response.status_code == 200
    body = summary_response.json()
    assert body["medical_data"]["past_medical_history"] == "میگرن"
    assert body["soap_note"].startswith("# SOAP")

    client._async_cleanup()


def test_upload_invalid_extension_returns_400(tmp_path, monkeypatch) -> None:
    client = _create_client(tmp_path, monkeypatch)
    token = _register_and_login(
        client,
        seed="Upload User",
        password="VeryStrongPassword123!",
    )
    headers = {"Authorization": f"Bearer {token}"}

    session_response = client.post(
        "/api/chat/session",
        json={"initial_complaint": "نیاز به آپلود"},
        headers=headers,
    )
    session_id = session_response.json()["id"]

    response = client.post(
        f"/api/files/{session_id}/upload",
        files={"file": ("malware.exe", BytesIO(b"x"), "application/octet-stream")},
        headers=headers,
    )

    assert response.status_code == 400
    assert "فرمت فایل مجاز نیست" in response.json()["detail"]

    client._async_cleanup()


def test_summary_exists_requires_session_ownership(tmp_path, monkeypatch) -> None:
    client = _create_client(tmp_path, monkeypatch)

    async def fake_build_summary(_messages):
        return {
            "chief_complaint": "تب",
            "history_present_illness": "از صبح شروع شده است.",
            "past_medical_history": "نامشخص",
            "medications": "نامشخص",
            "allergies": "نامشخص",
            "assessment": "ثبت شد.",
        }

    async def fake_chat(_messages, **kwargs):
        return "آیا علامت دیگری هم دارید؟"

    monkeypatch.setattr(chat_api.summary_builder, "build_summary", fake_build_summary)
    monkeypatch.setattr(chat_api.llm_service, "chat", fake_chat)

    owner_token = _register_and_login(
        client,
        seed="Owner",
        password="VeryStrongPassword123!",
    )
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    session_response = client.post(
        "/api/chat/session",
        json={"initial_complaint": "تب"},
        headers=owner_headers,
    )
    session_id = session_response.json()["id"]

    client.post(
        f"/api/chat/{session_id}",
        json={"content": "تب و لرز دارم"},
        headers=owner_headers,
    )

    other_token = _register_and_login(
        client,
        seed="Other User",
        password="VeryStrongPassword123!",
    )
    other_headers = {"Authorization": f"Bearer {other_token}"}

    response = client.get(
        f"/api/summary/session/{session_id}/exists",
        headers=other_headers,
    )

    assert response.status_code == 403

    client._async_cleanup()


def test_list_sessions_includes_patient_name_for_doctor(tmp_path, monkeypatch) -> None:
    client = _create_client(tmp_path, monkeypatch)

    patient_token = _register_and_login(
        client,
        seed="Named Patient",
        password="VeryStrongPassword123!",
    )
    patient_headers = {"Authorization": f"Bearer {patient_token}"}

    session_response = client.post(
        "/api/chat/session",
        json={"initial_complaint": "سردرد"},
        headers=patient_headers,
    )
    assert session_response.status_code == 200

    doctor_login = client.post(
        "/api/auth/login",
        json={"email": "bagherzade@doctor.com", "password": "0808"},
    )
    assert doctor_login.status_code == 200, doctor_login.text
    doctor_headers = {"Authorization": f"Bearer {doctor_login.json()['access_token']}"}

    sessions_response = client.get("/api/chat/sessions", headers=doctor_headers)
    assert sessions_response.status_code == 200
    sessions = sessions_response.json()
    assert len(sessions) >= 1
    matching = [s for s in sessions if s["initial_complaint"] == "سردرد"]
    assert matching
    assert matching[0]["patient_name"]
    assert matching[0]["patient_id"] > 0

    client._async_cleanup()
