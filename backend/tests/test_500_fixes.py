import pytest

from app.services.llm_service import llm_service
from app.services.summary_builder import summary_builder


def test_chat_message_and_summary_flow(client, monkeypatch):
    async def mock_chat(*args, **kwargs):
        return "چطور می‌توانم کمک کنم؟"

    async def mock_build_summary(*args, **kwargs):
        return {
            "chief_complaint": "سردرد",
            "history_present_illness": "از دیروز شروع شده",
            "past_medical_history": "نامشخص",
            "medications": "نامشخص",
            "allergies": "نامشخص",
            "assessment": "بررسی اولیه انجام شد",
        }

    monkeypatch.setattr(llm_service, "chat", mock_chat)
    monkeypatch.setattr(summary_builder, "build_summary", mock_build_summary)

    reg_res = client.post(
        "/api/auth/register",
        json={
            "national_id": "0499370899",
            "password": "password12345",
            "role": "patient",
        },
    )
    assert reg_res.status_code == 200

    login_res = client.post(
        "/api/auth/login",
        json={
            "national_id": "0499370899",
            "password": "password12345",
        },
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    session_res = client.post(
        "/api/chat/session",
        json={"initial_complaint": "I have a headache"},
        headers=headers,
    )
    assert session_res.status_code == 200
    session_id = session_res.json()["id"]

    msg_res = client.post(
        f"/api/chat/{session_id}",
        json={"content": "سلام"},
        headers=headers,
    )
    assert msg_res.status_code == 200
    assert msg_res.json()["role"] == "assistant"

    summary_res = client.get(f"/api/summary/{session_id}", headers=headers)
    assert summary_res.status_code == 200
    assert summary_res.json()["medical_data"]["chief_complaint"] == "سردرد"
