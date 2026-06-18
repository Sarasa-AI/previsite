from io import BytesIO

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.api.chat as chat_api
import app.db.database as database_module
import app.db.init_db as init_db_module
from app.db.database import Base, get_db
from app.main import app as fastapi_app
import app.models.summary


def _create_client(tmp_path, monkeypatch) -> TestClient:
    db_path = tmp_path / "test_mvp.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    monkeypatch.setattr(database_module, "engine", engine)
    monkeypatch.setattr(database_module, "SessionLocal", testing_session_local)
    monkeypatch.setattr(init_db_module, "engine", engine)

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    fastapi_app.dependency_overrides[get_db] = override_get_db

    client = TestClient(fastapi_app)
    return client


def _register_and_login(client: TestClient, *, name: str, password: str) -> str:
    register_response = client.post(
        "/api/auth/register",
        json={
            "name": name,
            "password": password,
            "role": "patient",
        },
    )
    assert register_response.status_code == 200

    login_response = client.post(
        "/api/auth/login",
        json={"name": name, "password": password},
    )
    assert login_response.status_code == 200
    return login_response.json()["access_token"]


def test_register_rejects_invalid_role(tmp_path, monkeypatch) -> None:
    client = _create_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/auth/register",
        json={
            "name": "Bad Role",
            "password": "VeryStrongPassword123!",
            "role": "visitor",
        },
    )

    assert response.status_code == 422
    fastapi_app.dependency_overrides.clear()
    client.close()


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

    async def fake_chat(_messages, system_prompt=None):
        if len(_messages) == 1:
            return "شدت سردرد از ۱ تا ۱۰ چقدر است؟"
        elif len(_messages) == 3:
            return "آیا حالت تهوع یا استفراغ هم دارید؟"
        elif len(_messages) == 5:
            return "ممنون از همکاری شما. اطلاعات کافی جمع‌آوری شد."
        elif len(_messages) == 7:
            return "ممنون از همکاری شما. اطلاعات کافی جمع‌آوری شد."
        return "پاسخ پیش‌فرض"

    async def fake_generate_soap_note(**_kwargs):
        return {
            "status": "success",
            "provider": "test",
            "soap_note": "# SOAP\n\nS: سردرد شدید\n\nA: نیاز به ارزیابی پزشک",
        }

    monkeypatch.setattr(chat_api.medical_extractor, "extract", fake_extract)
    monkeypatch.setattr(chat_api.summary_builder, "build_summary", fake_build_summary)
    monkeypatch.setattr(chat_api.llm_service, "chat", fake_chat)
    monkeypatch.setattr(chat_api.soap_generator, "generate_soap_note", fake_generate_soap_note)

    token = _register_and_login(
        client,
        name="Patient One",
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
    assert upload_response.json()["filename"] == "report.txt"

    summary_exists_response = client.get(
        f"/api/summary/session/{session_id}/exists",
        headers=headers,
    )
    assert summary_exists_response.status_code == 200
    assert summary_exists_response.json() == {"exists": True}

    summary_response = client.get(f"/api/summary/{session_id}", headers=headers)
    assert summary_response.status_code == 200
    body = summary_response.json()
    assert body["medical_data"]["past_medical_history"] == "میگرن"
    assert body["soap_note"].startswith("# SOAP")

    fastapi_app.dependency_overrides.clear()
    client.close()


def test_upload_invalid_extension_returns_400(tmp_path, monkeypatch) -> None:
    client = _create_client(tmp_path, monkeypatch)
    token = _register_and_login(
        client,
        name="Upload User",
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

    fastapi_app.dependency_overrides.clear()
    client.close()


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

    async def fake_chat(_messages):
        return "آیا علامت دیگری هم دارید؟"

    monkeypatch.setattr(chat_api.summary_builder, "build_summary", fake_build_summary)
    monkeypatch.setattr(chat_api.llm_service, "chat", fake_chat)

    owner_token = _register_and_login(
        client,
        name="Owner",
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
        name="Other User",
        password="VeryStrongPassword123!",
    )
    other_headers = {"Authorization": f"Bearer {other_token}"}

    response = client.get(
        f"/api/summary/session/{session_id}/exists",
        headers=other_headers,
    )

    assert response.status_code == 403

    fastapi_app.dependency_overrides.clear()
    client.close()
